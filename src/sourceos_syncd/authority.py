"""Authority dependency binding for sourceos-syncd.

Binds authority dependencies from the hybrid cybernetic control plane
to SourceOS state-integrity and local repair posture. Implements sourceos-syncd#27.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


AUTHORITY_KINDS = frozenset([
    "identity-authority",
    "policy-authority",
    "capability-authority",
    "memory-authority",
    "evidence-authority",
    "source-channel-authority",
])


@dataclass(frozen=True)
class AuthorityDependency:
    """A declared authority dependency for a state integrity lane."""

    authority_ref: str
    authority_kind: str
    lane_ref: str
    required: bool
    reachable: bool
    last_confirmed: str | None
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "authorityRef": self.authority_ref,
            "authorityKind": self.authority_kind,
            "laneRef": self.lane_ref,
            "required": self.required,
            "reachable": self.reachable,
            "lastConfirmed": self.last_confirmed,
            "note": self.note,
        }


@dataclass
class AuthorityReport:
    """Report of authority dependency health for the current device."""

    device_ref: str
    dependencies: list[AuthorityDependency] = field(default_factory=list)
    all_required_reachable: bool = False
    generated_at: str = field(default_factory=_now)
    note: str = "Stub — live authority checks deferred to sourceos-syncd daemon per sourceos-syncd#27."

    def to_dict(self) -> dict[str, Any]:
        return {
            "deviceRef": self.device_ref,
            "allRequiredReachable": self.all_required_reachable,
            "dependencies": [d.to_dict() for d in self.dependencies],
            "generatedAt": self.generated_at,
            "note": self.note,
        }


KNOWN_AUTHORITIES = {
    "identity-authority": "urn:srcos:authority:sovereign-identity:default",
    "policy-authority": "urn:srcos:authority:policy-fabric:default",
    "capability-authority": "urn:srcos:authority:capability-broker:default",
    "memory-authority": "urn:srcos:authority:memory-mesh:default",
    "evidence-authority": "urn:srcos:authority:agentplane:default",
    "source-channel-authority": "urn:srcos:authority:source-channel:default",
}


def stub_report(device_ref: str = "unknown") -> AuthorityReport:
    """Return a stub authority report when the daemon is not yet running."""
    deps = [
        AuthorityDependency(
            authority_ref=ref,
            authority_kind=kind,
            lane_ref="urn:srcos:lane:state-integrity:default",
            required=kind in ("identity-authority", "policy-authority"),
            reachable=False,
            last_confirmed=None,
            note="Stub — live authority probe deferred per sourceos-syncd#27.",
        )
        for kind, ref in KNOWN_AUTHORITIES.items()
    ]
    return AuthorityReport(device_ref=device_ref, dependencies=deps)


def check_authority(authority_kind: str, device_ref: str = "unknown") -> AuthorityDependency:
    """Probe a single authority dependency. Stub until daemon is live."""
    if authority_kind not in AUTHORITY_KINDS:
        raise ValueError(f"Unknown authority kind: {authority_kind}")
    ref = KNOWN_AUTHORITIES.get(authority_kind, f"urn:srcos:authority:{authority_kind}:default")
    return AuthorityDependency(
        authority_ref=ref,
        authority_kind=authority_kind,
        lane_ref="urn:srcos:lane:state-integrity:default",
        required=authority_kind in ("identity-authority", "policy-authority"),
        reachable=False,
        last_confirmed=None,
        note="Stub — live authority probe deferred per sourceos-syncd#27.",
    )
