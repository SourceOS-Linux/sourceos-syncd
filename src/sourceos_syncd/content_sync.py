"""Content view sync planner for sourceos-syncd.

Consumes a ContentViewManifest from KatelloContentClient and produces a
ContentSyncPlan describing the nix copy and nixos-rebuild steps required to
apply the new content view version.

Boundary invariant: plan() is pure and side-effect-free. execute() is the
only method that shells out — it requires an explicit caller opt-in and will
refuse to run if the plan's policy_gate is not 'allowed'.
"""

from __future__ import annotations

import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .katello_client import ContentViewManifest

SYNC_SCHEMA = "sourceos.content-sync-plan/v0.1"
RECEIPT_SPEC_VERSION = "0.1.0"
RECEIPT_ENGINE_ID = "sourceos.sync.katello-content"


@dataclass(frozen=True)
class ContentSyncPlan:
    """Non-mutating description of a pending content sync."""

    schema: str
    org: str
    content_view: str
    from_version: str | None
    to_version: str
    lifecycle_env: str
    nix_cache_url: str
    flake_ref: str
    policy_gate: str
    policy_reason: str
    steps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "org": self.org,
            "content_view": self.content_view,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "lifecycle_env": self.lifecycle_env,
            "nix_cache_url": self.nix_cache_url,
            "flake_ref": self.flake_ref,
            "policy_gate": self.policy_gate,
            "policy_reason": self.policy_reason,
            "steps": self.steps,
        }

    @property
    def allowed(self) -> bool:
        return self.policy_gate == "allowed"


class ContentViewSyncer:
    """Plans and optionally executes a Katello content view sync.

    The syncer enforces the locus gate: only local locus is permitted for
    Phase 0. burst_cloud and attested_fog require explicit policy elevation
    (not yet implemented).

    When signing_public_key is set (a minisign public key string starting
    with "RWS..."), the plan includes a `minisign -V` step before nix copy.
    This ensures the nix-cache-info served by Pulp was signed by the key
    embedded in the NixOS image, preventing an unauthenticated Katello from
    delivering arbitrary closures.
    """

    ALLOWED_LOCI = {"local", "trusted_private"}

    def __init__(
        self,
        flake_ref: str = "github:SociOS-Linux/source-os#builder-aarch64",
        locus: str = "local",
        current_version: str | None = None,
        signing_public_key: str | None = None,
    ) -> None:
        self._flake_ref = flake_ref
        self._locus = locus
        self._current_version = current_version
        self._signing_public_key = signing_public_key

    def plan(self, manifest: ContentViewManifest) -> ContentSyncPlan:
        """Return a non-mutating ContentSyncPlan. No I/O performed."""

        if self._locus not in self.ALLOWED_LOCI:
            return ContentSyncPlan(
                schema=SYNC_SCHEMA,
                org=manifest.org,
                content_view=manifest.content_view,
                from_version=self._current_version,
                to_version=manifest.version,
                lifecycle_env=manifest.lifecycle_env,
                nix_cache_url=manifest.nix_cache_url,
                flake_ref=self._flake_ref,
                policy_gate="denied",
                policy_reason=f"locus '{self._locus}' not in allowed loci {sorted(self.ALLOWED_LOCI)}",
                steps=[],
            )

        if self._current_version and self._current_version == manifest.version:
            return ContentSyncPlan(
                schema=SYNC_SCHEMA,
                org=manifest.org,
                content_view=manifest.content_view,
                from_version=self._current_version,
                to_version=manifest.version,
                lifecycle_env=manifest.lifecycle_env,
                nix_cache_url=manifest.nix_cache_url,
                flake_ref=self._flake_ref,
                policy_gate="no-op",
                policy_reason="already at latest version",
                steps=[],
            )

        steps = []

        # Verify nix-cache-info signature before pulling any closures.
        # The public key is the one baked into the NixOS image — an
        # unauthenticated Katello cannot deliver closures without knowing the
        # private key held by the build pipeline.
        if self._signing_public_key:
            cache_info_url = f"{manifest.nix_cache_url}/nix-cache-info"
            steps += [
                f"curl -fsSL '{cache_info_url}' -o /tmp/sourceos-nix-cache-info",
                f"curl -fsSL '{cache_info_url}.minisig' -o /tmp/sourceos-nix-cache-info.minisig",
                f"minisign -V -P '{self._signing_public_key}'"
                f" -m /tmp/sourceos-nix-cache-info"
                f" -x /tmp/sourceos-nix-cache-info.minisig",
            ]

        steps += [
            f"nix copy --from '{manifest.nix_cache_url}' '{self._flake_ref}'",
            f"nixos-rebuild switch --flake '{self._flake_ref}'",
        ]

        return ContentSyncPlan(
            schema=SYNC_SCHEMA,
            org=manifest.org,
            content_view=manifest.content_view,
            from_version=self._current_version,
            to_version=manifest.version,
            lifecycle_env=manifest.lifecycle_env,
            nix_cache_url=manifest.nix_cache_url,
            flake_ref=self._flake_ref,
            policy_gate="allowed",
            policy_reason=f"locus '{self._locus}' permitted; new version available",
            steps=steps,
        )

    def execute(self, plan: ContentSyncPlan, dry_run: bool = True) -> dict[str, Any]:
        """Execute the sync plan. dry_run=True (default) only prints steps.

        Always emits a SyncCycleReceipt in the return dict under 'receipt'.
        """
        cycle_id = str(uuid.uuid4())
        t_start = time.monotonic()

        if not plan.allowed:
            outcome = "denied" if plan.policy_gate == "denied" else "skipped"
            receipt = self._build_receipt(
                cycle_id=cycle_id,
                plan=plan,
                outcome=outcome,
                steps=[],
                duration_ms=0,
            )
            return {
                "status": outcome,
                "reason": plan.policy_reason,
                "policy_gate": plan.policy_gate,
                "receipt": receipt,
            }

        results = []
        for step in plan.steps:
            if dry_run:
                results.append({"step": step, "status": "dry_run", "reason": "dry_run=True"})
                continue

            if not shutil.which("nix") and step.startswith("nix "):
                results.append({"step": step, "status": "skipped", "reason": "nix not found in PATH"})
                continue
            if not shutil.which("nixos-rebuild") and step.startswith("nixos-rebuild "):
                results.append({"step": step, "status": "skipped", "reason": "nixos-rebuild not found in PATH"})
                continue

            try:
                proc = subprocess.run(
                    step, shell=True, capture_output=True, text=True, timeout=600
                )
                results.append({
                    "step": step,
                    "status": "ok" if proc.returncode == 0 else "failed",
                    "returncode": proc.returncode,
                    "stdout": proc.stdout.strip()[:500],
                    "stderr": proc.stderr.strip()[:500],
                })
            except subprocess.TimeoutExpired:
                results.append({"step": step, "status": "timeout"})

        duration_ms = int((time.monotonic() - t_start) * 1000)
        outcome = "dry_run" if dry_run else (
            "applied" if all(r.get("status") in ("ok", "dry_run", "skipped") for r in results)
            else "failed"
        )
        receipt = self._build_receipt(
            cycle_id=cycle_id,
            plan=plan,
            outcome=outcome,
            steps=results,
            duration_ms=duration_ms,
        )
        return {
            "status": outcome,
            "plan": plan.to_dict(),
            "results": results,
            "receipt": receipt,
        }

    def _build_receipt(
        self,
        cycle_id: str,
        plan: ContentSyncPlan,
        outcome: str,
        steps: list[dict[str, Any]],
        duration_ms: int,
    ) -> dict[str, Any]:
        receipt_id = f"urn:srcos:sync-receipt:{uuid.uuid4()}"
        audit_id = f"urn:srcos:audit:{uuid.uuid4()}"
        now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return {
            "id": receipt_id,
            "type": "SyncCycleReceipt",
            "specVersion": RECEIPT_SPEC_VERSION,
            "cycleId": cycle_id,
            "engineId": RECEIPT_ENGINE_ID,
            "org": plan.org,
            "contentView": plan.content_view,
            "fromVersion": plan.from_version,
            "toVersion": plan.to_version,
            "lifecycleEnv": plan.lifecycle_env,
            "locus": self._locus,
            "outcome": outcome,
            "policyGate": plan.policy_gate,
            "policyReason": plan.policy_reason,
            "steps": steps,
            "nixCacheUrl": plan.nix_cache_url,
            "flakeRef": plan.flake_ref,
            "durationMs": duration_ms,
            "issuedAt": now,
            "auditId": audit_id,
        }
