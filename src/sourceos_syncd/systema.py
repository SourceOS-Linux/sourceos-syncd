"""Systema integration for sourceos-syncd.

Implements sourceos-syncd's Systema role: local-first state membranes,
source-confidence event mapping, and projection-aware operator narratives.

Maps ProCybernetica's source-confidence, projection-loss, membrane-boundary,
and capability-radius profiles to existing SourceOS schemas without introducing
new schemas (uses ProvenanceRecord, ValidatorReceipt, ReasoningAssay,
StaleStateRecord from sourceos-spec). Implements issue sourceos-syncd#20.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# Systema membrane kinds
MEMBRANE_KINDS = frozenset([
    "activation",
    "side-effect",
    "storage",
])

# Systema membrane decisions
MEMBRANE_DECISIONS = frozenset([
    "admitted",
    "blocked",
    "revoked",
    "applied",
    "suppressed",
    "transformed",
    "mounted",
    "refused",
])


@dataclass(frozen=True)
class SourceConfidenceMapping:
    """Maps Systema source-confidence score to SourceOS staleness/exactness contracts."""

    confidence: float

    @property
    def sourceos_class(self) -> str:
        if self.confidence >= 0.85:
            return "verifier-required"
        if self.confidence >= 0.70:
            return "user-confirmed"
        if self.confidence >= 0.50:
            return "ambient-host"
        return "stale-context-injection"

    @property
    def admission_policy(self) -> str:
        if self.confidence >= 0.85:
            return "verifier-required"
        if self.confidence >= 0.70:
            return "user-confirmed"
        return "cryptographic-proof"

    @property
    def staleness_risk(self) -> str:
        if self.confidence >= 0.85:
            return "none"
        if self.confidence >= 0.70:
            return "low"
        if self.confidence >= 0.50:
            return "medium"
        return "high"

    @property
    def suppress_mutation(self) -> bool:
        return self.confidence < 0.50

    def to_dict(self) -> dict[str, Any]:
        return {
            "confidence": self.confidence,
            "sourceosClass": self.sourceos_class,
            "admissionPolicy": self.admission_policy,
            "stalenessRisk": self.staleness_risk,
            "suppressMutation": self.suppress_mutation,
        }


@dataclass(frozen=True)
class MembraneEvent:
    """A Systema membrane boundary event mapped to SourceOS contracts."""

    membrane_kind: str
    decision: str
    subject_ref: str
    actor_ref: str
    confidence: float
    policy_decision_ref: str | None
    observed_at: str = field(default_factory=_now)

    @property
    def confidence_mapping(self) -> SourceConfidenceMapping:
        return SourceConfidenceMapping(self.confidence)

    def to_dict(self) -> dict[str, Any]:
        return {
            "membraneKind": self.membrane_kind,
            "decision": self.decision,
            "subjectRef": self.subject_ref,
            "actorRef": self.actor_ref,
            "confidence": self.confidence,
            "confidenceMapping": self.confidence_mapping.to_dict(),
            "policyDecisionRef": self.policy_decision_ref,
            "observedAt": self.observed_at,
        }


# Capability radius levels (R0–R5)
CAPABILITY_RADIUS_DESCRIPTIONS = {
    0: "observe-only — no side effects, no network, no file writes",
    1: "local-read — file-read from allowed paths, no writes",
    2: "local-write — file-read + controlled file-write to workspace",
    3: "local-execute — process-spawn within policy constraints",
    4: "network-local — TCP to localhost/LAN, no internet",
    5: "internet-connected — full network egress, policy-gated",
}


@dataclass(frozen=True)
class CapabilityRadiusProfile:
    """Maps a Systema capability radius to Agent Machine contracts."""

    radius: int
    agent_ref: str

    @property
    def description(self) -> str:
        return CAPABILITY_RADIUS_DESCRIPTIONS.get(self.radius, "unknown")

    @property
    def capability_contract_kind(self) -> str:
        map_ = {0: "observe-only", 1: "read-local", 2: "write-local", 3: "execute-local", 4: "network-local", 5: "network-internet"}
        return map_.get(self.radius, "unknown")

    @property
    def fail_closed(self) -> bool:
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "radius": self.radius,
            "agentRef": self.agent_ref,
            "description": self.description,
            "capabilityContractKind": self.capability_contract_kind,
            "failClosed": self.fail_closed,
        }


def map_confidence(confidence: float) -> SourceConfidenceMapping:
    return SourceConfidenceMapping(confidence)


def map_membrane_event(
    membrane_kind: str,
    decision: str,
    subject_ref: str,
    actor_ref: str,
    confidence: float,
    policy_decision_ref: str | None = None,
) -> MembraneEvent:
    if membrane_kind not in MEMBRANE_KINDS:
        raise ValueError(f"Unknown membrane kind: {membrane_kind}")
    if decision not in MEMBRANE_DECISIONS:
        raise ValueError(f"Unknown membrane decision: {decision}")
    return MembraneEvent(
        membrane_kind=membrane_kind,
        decision=decision,
        subject_ref=subject_ref,
        actor_ref=actor_ref,
        confidence=confidence,
        policy_decision_ref=policy_decision_ref,
    )


def capability_radius(radius: int, agent_ref: str) -> CapabilityRadiusProfile:
    if not (0 <= radius <= 5):
        raise ValueError(f"Capability radius must be 0–5, got {radius}")
    return CapabilityRadiusProfile(radius=radius, agent_ref=agent_ref)
