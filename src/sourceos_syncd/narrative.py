"""Operator narrative and SocioSphere dashboard contract for sourceos-syncd.

Converts canonical evidence and State Integrity Reports into legible operator
cards for the SocioSphere dashboard. Implements issue sourceos-syncd#9.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


CARD_KIND_MAP = {
    "state-integrity-violation": "operator-alert",
    "policy-violation": "operator-alert",
    "repair-required": "operator-action",
    "conflict-detected": "operator-review",
    "repair-completed": "operator-info",
    "sync-ok": "operator-status",
    "identity-confirmed": "operator-status",
    "org-policy-loaded": "operator-status",
}


@dataclass
class OperatorCard:
    """A legible operator-facing card for the SocioSphere dashboard."""

    card_id: str
    kind: str
    severity: str
    title: str
    summary: str
    subject_ref: str
    evidence_ref: str | None
    policy_decision_ref: str | None
    action_required: bool
    action_label: str | None
    generated_at: str
    source_event_ref: str | None = None
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "cardId": self.card_id,
            "kind": self.kind,
            "severity": self.severity,
            "title": self.title,
            "summary": self.summary,
            "subjectRef": self.subject_ref,
            "evidenceRef": self.evidence_ref,
            "policyDecisionRef": self.policy_decision_ref,
            "actionRequired": self.action_required,
            "actionLabel": self.action_label,
            "generatedAt": self.generated_at,
            "sourceEventRef": self.source_event_ref,
            "note": self.note,
        }


@dataclass
class NarrativeSummary:
    """Operator-facing narrative summary of the current state."""

    device_ref: str
    profile_ref: str | None
    workspace_ref: str | None
    overall_status: str
    cards: list[OperatorCard] = field(default_factory=list)
    generated_at: str = field(default_factory=_now)
    note: str = "Stub — live sourceos-syncd daemon required for full narrative per sourceos-syncd#9."

    def to_dict(self) -> dict[str, Any]:
        return {
            "deviceRef": self.device_ref,
            "profileRef": self.profile_ref,
            "workspaceRef": self.workspace_ref,
            "overallStatus": self.overall_status,
            "cards": [c.to_dict() for c in self.cards],
            "generatedAt": self.generated_at,
            "note": self.note,
        }


def _card_id(prefix: str) -> str:
    ts = _now().replace(":", "").replace("-", "").replace("T", "").replace("Z", "")
    return f"urn:srcos:operator-card:{prefix}:{ts}"


def card_from_event(event: dict[str, Any]) -> OperatorCard | None:
    """Convert a state integrity event to an operator card. Returns None if not surfaceable."""
    kind = event.get("kind", "")
    card_kind = CARD_KIND_MAP.get(kind)
    if card_kind is None:
        return None

    severity = "critical" if kind in ("state-integrity-violation", "policy-violation") else "warning" if kind in ("repair-required", "conflict-detected") else "info"
    action_required = kind in ("repair-required", "conflict-detected", "policy-violation")

    return OperatorCard(
        card_id=_card_id(kind),
        kind=card_kind,
        severity=severity,
        title=kind.replace("-", " ").title(),
        summary=event.get("body", event.get("summary", kind)),
        subject_ref=event.get("subjectRef", event.get("subject_ref", "unknown")),
        evidence_ref=event.get("evidenceRef", event.get("evidence_ref")),
        policy_decision_ref=event.get("policyDecisionRef", event.get("policy_decision_ref")),
        action_required=action_required,
        action_label="Review and approve repair" if action_required else None,
        generated_at=_now(),
        source_event_ref=event.get("id"),
    )


def narrative_from_report(report: dict[str, Any]) -> NarrativeSummary:
    """Build a NarrativeSummary from a State Integrity Report."""
    overall = report.get("status", "unknown")
    cards = []

    for item in report.get("violations", []):
        card = card_from_event({
            "kind": "state-integrity-violation",
            "body": item.get("description", "State integrity violation"),
            "subjectRef": item.get("subjectRef", "unknown"),
            "evidenceRef": item.get("evidenceRef"),
            "policyDecisionRef": item.get("policyDecisionRef"),
        })
        if card:
            cards.append(card)

    for item in report.get("repairs", []):
        card = card_from_event({
            "kind": "repair-required",
            "body": item.get("description", "Repair required"),
            "subjectRef": item.get("subjectRef", "unknown"),
        })
        if card:
            cards.append(card)

    return NarrativeSummary(
        device_ref=report.get("deviceRef", "unknown"),
        profile_ref=report.get("profileRef"),
        workspace_ref=report.get("workspaceRef"),
        overall_status=overall,
        cards=cards,
    )


def stub_narrative(device_ref: str = "unknown") -> NarrativeSummary:
    """Return a stub narrative when the daemon is not yet running."""
    return NarrativeSummary(
        device_ref=device_ref,
        profile_ref=None,
        workspace_ref=None,
        overall_status="unavailable",
        cards=[],
    )
