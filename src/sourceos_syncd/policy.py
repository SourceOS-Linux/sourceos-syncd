"""PolicyFabric-compatible decision hook stubs for sourceos-syncd.

The real PolicyFabric service will eventually own policy evaluation. This module
provides a local, deterministic contract-compatible evaluator so State Integrity
Reports can already carry policy counts and explanation codes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

POLICY_DECISION_SCHEMA = "sourceos.policy-decision/v1alpha1"
POLICY_ENGINE = "policy-fabric-local-stub"

ACTIONS = {
    "index",
    "retain",
    "replicate",
    "agent_access",
    "repair_preview",
    "purge_preview",
    "read",
    "write",
}

STATUSES = {"allowed", "denied", "redacted", "deferred"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class PolicyRequest:
    action: str
    lane: str
    subject: str = "sourceos-syncd"
    object_id: str | None = None
    data_class: str = "internal"
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PolicyDecision:
    decision_id: str
    action: str
    lane: str
    status: str
    reason: str
    subject: str
    object_id: str | None
    data_class: str
    engine: str = POLICY_ENGINE
    schema: str = POLICY_DECISION_SCHEMA
    generated_at: str = field(default_factory=utc_now)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "decision_id": self.decision_id,
            "generated_at": self.generated_at,
            "engine": self.engine,
            "action": self.action,
            "lane": self.lane,
            "status": self.status,
            "reason": self.reason,
            "subject": self.subject,
            "object_id": self.object_id,
            "data_class": self.data_class,
        }


def _decision_id(request: PolicyRequest, status: str, reason: str) -> str:
    payload = {
        "action": request.action,
        "lane": request.lane,
        "subject": request.subject,
        "object_id": request.object_id,
        "data_class": request.data_class,
        "status": status,
        "reason": reason,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return f"policy-{digest}"


def evaluate_policy(request: PolicyRequest) -> PolicyDecision:
    """Evaluate a local policy request with conservative SourceOS defaults."""
    if request.action not in ACTIONS:
        status = "deferred"
        reason = "unknown_action"
    elif request.lane == "secure" and request.action in {"agent_access", "replicate"}:
        status = "denied"
        reason = "secure_lane_requires_explicit_grant"
    elif request.lane == "secure" and request.action == "index":
        status = "redacted"
        reason = "secure_lane_indexing_requires_redaction"
    elif request.lane == "repair" and request.action in {"agent_access", "write"}:
        status = "denied"
        reason = "repair_lane_is_quarantine_scoped"
    elif request.lane == "ephemeral" and request.action == "retain":
        status = "deferred"
        reason = "ephemeral_retention_requires_ttl"
    elif request.data_class in {"secret", "credential"} and request.action in {"replicate", "agent_access"}:
        status = "denied"
        reason = "sensitive_data_requires_explicit_grant"
    else:
        status = "allowed"
        reason = "default_local_policy_allows"

    return PolicyDecision(
        decision_id=_decision_id(request, status, reason),
        action=request.action,
        lane=request.lane,
        status=status,
        reason=reason,
        subject=request.subject,
        object_id=request.object_id,
        data_class=request.data_class,
    )


def evaluate_report_policy(lanes: list[dict[str, Any]], subject: str = "sourceos-syncd") -> list[dict[str, Any]]:
    """Generate representative decisions for every lane in a report."""
    decisions: list[dict[str, Any]] = []
    for lane in lanes:
        lane_name = str(lane.get("name", "normal"))
        for action in ("index", "retain", "replicate", "agent_access"):
            decision = evaluate_policy(PolicyRequest(action=action, lane=lane_name, subject=subject))
            decisions.append(decision.as_dict())
    return decisions


def decision_counts(decisions: list[dict[str, Any]]) -> dict[str, int]:
    counts = {status: 0 for status in sorted(STATUSES)}
    for decision in decisions:
        status = str(decision.get("status", "deferred"))
        if status not in counts:
            status = "deferred"
        counts[status] += 1
    return counts


def policy_summary(decisions: list[dict[str, Any]], sample_limit: int = 12) -> dict[str, Any]:
    return {
        "engine": POLICY_ENGINE,
        "counts": decision_counts(decisions),
        "sample": decisions[:sample_limit],
    }
