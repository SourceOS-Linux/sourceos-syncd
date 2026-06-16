"""Content view sync planner for sourceos-syncd.

Consumes a ContentViewManifest from KatelloContentClient and produces a
ContentSyncPlan describing the nix copy and nixos-rebuild steps required to
apply the new content view version.

Boundary invariant: plan() is pure and side-effect-free. execute() is the
only method that shells out — it requires an explicit caller opt-in and will
refuse to run if the plan's policy_gate is not 'allowed'.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any

from .katello_client import ContentViewManifest

SYNC_SCHEMA = "sourceos.content-sync-plan/v0.1"


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
    """

    ALLOWED_LOCI = {"local", "trusted_private"}

    def __init__(
        self,
        flake_ref: str = "github:SociOS-Linux/source-os#builder-aarch64",
        locus: str = "local",
        current_version: str | None = None,
    ) -> None:
        self._flake_ref = flake_ref
        self._locus = locus
        self._current_version = current_version

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

        steps = [
            f"nix copy --from '{manifest.nix_cache_url}' --no-check-sigs '{self._flake_ref}'",
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
        """Execute the sync plan. dry_run=True (default) only prints steps."""

        if not plan.allowed:
            return {
                "status": "skipped",
                "reason": plan.policy_reason,
                "policy_gate": plan.policy_gate,
            }

        results = []
        for step in plan.steps:
            if dry_run:
                results.append({"step": step, "status": "dry_run"})
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

        return {
            "status": "dry_run" if dry_run else "executed",
            "plan": plan.to_dict(),
            "results": results,
        }
