"""AgentPlane-compatible trust gate for SourceOS State Integrity Reports."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .evidence import digest_json
from .reports import diagnose, validate_report

TRUST_DECISION_SCHEMA = "sourceos.agent-trust-decision/v1alpha1"
TRUST_ENGINE = "agentplane-local-trust-gate"

TRUST_STATUSES = {"allowed", "degraded_allowed", "blocked", "unknown"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class TrustRequest:
    subject: str
    action: str
    lane: str = "normal"
    allow_degraded: bool = False
    require_attestation: bool = False
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TrustDecision:
    decision_id: str
    status: str
    reason: str
    subject: str
    action: str
    lane: str
    report_digest: str
    report_status: str
    allow_degraded: bool
    require_attestation: bool
    engine: str = TRUST_ENGINE
    schema: str = TRUST_DECISION_SCHEMA
    generated_at: str = field(default_factory=utc_now)
    evidence: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "decision_id": self.decision_id,
            "generated_at": self.generated_at,
            "engine": self.engine,
            "subject": self.subject,
            "action": self.action,
            "lane": self.lane,
            "status": self.status,
            "reason": self.reason,
            "report_digest": self.report_digest,
            "report_status": self.report_status,
            "allow_degraded": self.allow_degraded,
            "require_attestation": self.require_attestation,
            "evidence": self.evidence,
        }


def _decision_id(seed: dict[str, Any]) -> str:
    digest = hashlib.sha256(json.dumps(seed, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:20]
    return f"trust-{digest}"


def evaluate_trust(report: dict[str, Any], request: TrustRequest) -> dict[str, Any]:
    """Evaluate whether an agent should use a state substrate represented by a report."""
    contract_errors = validate_report(report)
    diagnosis = diagnose(report)
    report_status = diagnosis.get("status", "unknown")
    report_digest = digest_json(report)
    attestation = report.get("attestation", {}) if isinstance(report.get("attestation"), dict) else {}
    attested = bool(attestation.get("signed"))
    lane_names = {lane.get("name") for lane in report.get("lanes", []) if isinstance(lane, dict)}

    status = "allowed"
    reason = "state_integrity_allows_agent_action"

    if contract_errors:
        status = "blocked"
        reason = "report_contract_invalid"
    elif request.lane not in lane_names:
        status = "blocked"
        reason = "requested_lane_missing"
    elif request.require_attestation and not attested:
        status = "blocked"
        reason = "required_attestation_missing"
    elif report_status == "unsafe":
        status = "blocked"
        reason = "report_status_unsafe"
    elif report_status in {"stale", "unknown"}:
        status = "blocked"
        reason = "report_status_not_trusted"
    elif report_status == "degraded" and request.allow_degraded:
        status = "degraded_allowed"
        reason = "degraded_mode_explicitly_allowed"
    elif report_status == "degraded":
        status = "blocked"
        reason = "degraded_mode_requires_explicit_allowance"

    policy_counts = report.get("policy", {}).get("policy_decisions", {}) if isinstance(report.get("policy"), dict) else {}
    if status in {"allowed", "degraded_allowed"} and request.lane in {"secure", "repair"}:
        if policy_counts.get("denied", 0) > 0:
            status = "blocked"
            reason = "policy_counts_indicate_restricted_lane"

    evidence = {
        "contract_errors": contract_errors,
        "diagnosis": diagnosis,
        "attestation_signed": attested,
        "available_lanes": sorted(str(name) for name in lane_names if name),
        "policy_counts": policy_counts,
    }
    seed = {
        "subject": request.subject,
        "action": request.action,
        "lane": request.lane,
        "status": status,
        "reason": reason,
        "report_digest": report_digest,
        "allow_degraded": request.allow_degraded,
        "require_attestation": request.require_attestation,
    }
    return TrustDecision(
        decision_id=_decision_id(seed),
        status=status,
        reason=reason,
        subject=request.subject,
        action=request.action,
        lane=request.lane,
        report_digest=report_digest,
        report_status=str(report_status),
        allow_degraded=request.allow_degraded,
        require_attestation=request.require_attestation,
        evidence=evidence,
    ).as_dict()


def validate_trust_decision(decision: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {
        "schema",
        "decision_id",
        "generated_at",
        "engine",
        "subject",
        "action",
        "lane",
        "status",
        "reason",
        "report_digest",
        "report_status",
        "allow_degraded",
        "require_attestation",
        "evidence",
    }
    missing = sorted(required - set(decision))
    if missing:
        errors.append(f"missing trust decision keys: {', '.join(missing)}")
    if decision.get("schema") != TRUST_DECISION_SCHEMA:
        errors.append(f"unsupported trust decision schema: {decision.get('schema')!r}")
    if decision.get("status") not in TRUST_STATUSES:
        errors.append("status is invalid")
    if not str(decision.get("report_digest", "")).startswith("sha256:"):
        errors.append("report_digest must start with sha256:")
    if not isinstance(decision.get("allow_degraded"), bool):
        errors.append("allow_degraded must be boolean")
    if not isinstance(decision.get("require_attestation"), bool):
        errors.append("require_attestation must be boolean")
    if not isinstance(decision.get("evidence"), dict):
        errors.append("evidence must be an object")
    return errors
