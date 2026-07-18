"""SourceOS Metadata Coherence Plane for sourceos-syncd.

The typed reconciliation layer for filesystem, registry, extension, container,
persona, cache, privacy, process, and index state. Implements sourceos-syncd#23.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


COHERENCE_DOMAINS = [
    "filesystem",
    "registry",
    "extension",
    "container",
    "persona",
    "cache",
    "privacy",
    "process",
    "index",
]


@dataclass(frozen=True)
class CoherenceState:
    """Coherence state for a single domain."""

    domain: str
    status: str
    last_checked: str
    conflict_count: int
    repair_eligible: int
    human_review_required: int
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "status": self.status,
            "lastChecked": self.last_checked,
            "conflictCount": self.conflict_count,
            "repairEligible": self.repair_eligible,
            "humanReviewRequired": self.human_review_required,
            "note": self.note,
        }


@dataclass
class CoherencePlaneSnapshot:
    """Full snapshot of the Metadata Coherence Plane."""

    device_ref: str
    domains: list[CoherenceState] = field(default_factory=list)
    overall_status: str = "unavailable"
    generated_at: str = field(default_factory=_now)
    note: str = "Stub — sourceos-syncd daemon not yet running; coherence scan deferred per sourceos-syncd#23."

    def to_dict(self) -> dict[str, Any]:
        return {
            "deviceRef": self.device_ref,
            "overallStatus": self.overall_status,
            "domains": [d.to_dict() for d in self.domains],
            "generatedAt": self.generated_at,
            "note": self.note,
        }


@dataclass(frozen=True)
class CoherenceConflict:
    """A single coherence conflict in a domain."""

    conflict_ref: str
    domain: str
    object_ref: str
    staleness_class: str
    auto_repair_eligible: bool
    human_review_required: bool
    local_value_redacted: bool
    remote_source_ref: str
    observed_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "conflictRef": self.conflict_ref,
            "domain": self.domain,
            "objectRef": self.object_ref,
            "stalenessClass": self.staleness_class,
            "autoRepairEligible": self.auto_repair_eligible,
            "humanReviewRequired": self.human_review_required,
            "localValueRedacted": self.local_value_redacted,
            "remoteSourceRef": self.remote_source_ref,
            "observedAt": self.observed_at,
        }


def stub_snapshot(device_ref: str = "unknown") -> CoherencePlaneSnapshot:
    """Return a stub snapshot with all domains in unavailable state."""
    domains = [
        CoherenceState(
            domain=d,
            status="unavailable",
            last_checked=_now(),
            conflict_count=0,
            repair_eligible=0,
            human_review_required=0,
        )
        for d in COHERENCE_DOMAINS
    ]
    return CoherencePlaneSnapshot(device_ref=device_ref, domains=domains)


def scan_domain(domain: str, device_ref: str = "unknown") -> CoherenceState:
    """Scan a single coherence domain. Stub until daemon is live."""
    if domain not in COHERENCE_DOMAINS:
        raise ValueError(f"Unknown coherence domain: {domain}. Valid: {COHERENCE_DOMAINS}")
    return CoherenceState(
        domain=domain,
        status="unavailable",
        last_checked=_now(),
        conflict_count=0,
        repair_eligible=0,
        human_review_required=0,
        note="Stub — live scan deferred to sourceos-syncd daemon per sourceos-syncd#23.",
    )
