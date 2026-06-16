"""Daemon mode for sourceos-syncd.

Polls Katello on a configurable interval. When a new content view version
is available, plans and applies the sync, then persists the SyncCycleReceipt
and updates the current-version state file.

Failure handling:
  - A failed sync (outcome: failed) is logged to stderr and the version file
    is NOT updated, so the next poll will retry.
  - A denied or skipped sync is logged but not retried (policy won't change
    without operator intervention).
  - Network/API errors are caught; the daemon backs off exponentially up to
    MAX_BACKOFF_S and retries indefinitely.

The daemon is intentionally simple: no threading, no async, one poll loop.
systemd handles restart-on-crash via Restart=on-failure.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
import time
from typing import Any

from .content_sync import ContentViewSyncer
from .katello_client import KatelloContentClient
from .receipt_store import ReceiptStore

log = logging.getLogger("sourceos-syncd.daemon")

DEFAULT_POLL_INTERVAL_S = 300
MIN_BACKOFF_S = 30
MAX_BACKOFF_S = 1800


class SyncDaemon:
    def __init__(
        self,
        katello_url: str,
        katello_user: str,
        katello_password: str,
        org: str,
        content_view: str,
        lifecycle_env: str,
        locus: str,
        flake_ref: str,
        poll_interval_s: int = DEFAULT_POLL_INTERVAL_S,
        store_root: str | None = None,
        verify_ssl: bool = True,
        signing_public_key: str | None = None,
        agentplane_run_ref: str | None = None,
    ) -> None:
        self._client = KatelloContentClient(
            base_url=katello_url,
            username=katello_user,
            password=katello_password,
            org=org,
            verify_ssl=verify_ssl,
        )
        self._content_view = content_view
        self._lifecycle_env = lifecycle_env
        self._locus = locus
        self._flake_ref = flake_ref
        self._signing_public_key = signing_public_key
        self._agentplane_run_ref = agentplane_run_ref
        self._poll_interval_s = poll_interval_s
        self._store = ReceiptStore(root=store_root or "/var/lib/sourceos-syncd")
        self._running = True
        self._backoff_s = 0

        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    def _handle_signal(self, signum: int, _frame: Any) -> None:
        log.info("received signal %d, shutting down", signum)
        self._running = False

    def run(self) -> int:
        self._store.ensure_dirs()
        log.info(
            "daemon starting — org=%s cv=%s env=%s locus=%s poll=%ds",
            self._client._org,
            self._content_view,
            self._lifecycle_env,
            self._locus,
            self._poll_interval_s,
        )

        while self._running:
            try:
                self._poll_once()
                self._backoff_s = 0
            except Exception as exc:  # noqa: BLE001
                self._backoff_s = min(
                    MAX_BACKOFF_S,
                    self._backoff_s * 2 if self._backoff_s else MIN_BACKOFF_S,
                )
                log.error("poll error (%s: %s); backing off %ds", type(exc).__name__, exc, self._backoff_s)

            if not self._running:
                break

            sleep_s = self._backoff_s or self._poll_interval_s
            log.debug("sleeping %ds", sleep_s)
            self._interruptible_sleep(sleep_s)

        log.info("daemon stopped")
        return 0

    def _poll_once(self) -> None:
        current_version = self._store.read_current_version()
        manifest = self._client.get_latest_version(self._content_view, self._lifecycle_env)

        syncer = ContentViewSyncer(
            flake_ref=self._flake_ref,
            locus=self._locus,
            current_version=current_version,
            signing_public_key=self._signing_public_key,
            agentplane_run_ref=self._agentplane_run_ref,
        )
        plan = syncer.plan(manifest)

        if plan.policy_gate == "no-op":
            log.debug("already at %s — no sync needed", manifest.version)
            return

        log.info(
            "syncing %s → %s (locus=%s gate=%s)",
            current_version or "none",
            manifest.version,
            self._locus,
            plan.policy_gate,
        )

        result = syncer.execute(plan, dry_run=False)
        receipt = result.get("receipt", {})

        receipt_path = self._store.write_receipt(receipt)
        log.info("receipt written: %s (outcome=%s)", receipt_path, receipt.get("outcome"))

        if result.get("status") == "applied":
            self._store.write_current_version(manifest.version)
            log.info("applied version %s", manifest.version)
        elif result.get("status") in ("denied", "skipped"):
            log.warning(
                "sync %s: %s — will not retry until policy changes",
                result["status"],
                receipt.get("policyReason", ""),
            )
        elif result.get("status") == "failed":
            log.error("sync failed — will retry next poll; receipt: %s", receipt_path)
            raise RuntimeError(f"sync failed for version {manifest.version}")

    def _interruptible_sleep(self, seconds: int) -> None:
        deadline = time.monotonic() + seconds
        while self._running and time.monotonic() < deadline:
            time.sleep(min(5, deadline - time.monotonic()))


def _resolve_password() -> str:
    """Read password from KATELLO_PASSWORD or KATELLO_PASSWORD_FILE.

    KATELLO_PASSWORD_FILE wins when both are set. This supports systemd
    LoadCredential which writes the secret to a file, not an env var.
    """
    pw_file = os.environ.get("KATELLO_PASSWORD_FILE", "")
    if pw_file:
        try:
            return open(pw_file, encoding="utf-8").read().strip()
        except OSError as exc:
            raise RuntimeError(f"cannot read KATELLO_PASSWORD_FILE {pw_file}: {exc}") from exc
    pw = os.environ.get("KATELLO_PASSWORD", "")
    if not pw:
        raise RuntimeError("KATELLO_PASSWORD or KATELLO_PASSWORD_FILE must be set")
    return pw


def daemon_from_env() -> SyncDaemon:
    """Construct a SyncDaemon entirely from environment variables."""
    return SyncDaemon(
        katello_url=os.environ.get("KATELLO_URL", "https://127.0.0.1:8443"),
        katello_user=os.environ.get("KATELLO_USER", "admin"),
        katello_password=_resolve_password(),
        org=os.environ.get("KATELLO_ORG", "SocioProphet"),
        content_view=os.environ.get("KATELLO_CONTENT_VIEW", "sourceos-builder-aarch64"),
        lifecycle_env=os.environ.get("KATELLO_LIFECYCLE_ENV", "stable"),
        locus=os.environ.get("SOURCEOS_LOCUS", "local"),
        flake_ref=os.environ.get(
            "SOURCEOS_FLAKE_REF", "github:SociOS-Linux/source-os#builder-aarch64"
        ),
        signing_public_key=os.environ.get("SOURCEOS_SIGNING_PUBLIC_KEY", "") or None,
        poll_interval_s=int(os.environ.get("SOURCEOS_POLL_INTERVAL", str(DEFAULT_POLL_INTERVAL_S))),
        store_root=os.environ.get("SOURCEOS_STORE_ROOT", "/var/lib/sourceos-syncd"),
        verify_ssl=os.environ.get("SOURCEOS_NO_VERIFY_SSL", "").lower() not in ("1", "true", "yes"),
    )
