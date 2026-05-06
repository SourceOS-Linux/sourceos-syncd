"""Delivery Excellence scorecards for SourceOS State Integrity Reports."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .evidence import digest_json
from .reports import diagnose, validate_report, verify

SCORECARD_SCHEMA = "sourceos.delivery-scorecard/v1alpha1"
SCORECARD_ENGINE = "delivery-excellence-local-scorecard"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class Scorecard:
    scorecard_id: str
    component: str
    status: str
    score: int
    report_digest: str
    summary: str
    dimensions: dict[str, Any]
    gates: list[dict[str, Any]]
    engine: str = SCORECARD_ENGINE
    schema: str = SCORECARD_SCHEMA
    generated_at: str = field(default_factory=utc_now)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "scorecard_id": self.scorecard_id,
            "generated_at": self.generated_at,
            "engine": self.engine,
            "component": self.component,
            "status": self.status,
            "score": self.score,
            "report_digest": self.report_digest,
            "summary": self.summary,
            "dimensions": self.dimensions,
            "gates": self.gates,
        }


def _scorecard_id(report_digest: str, component: str, status: str) -> str:
    seed = {"report_digest": report_digest, "component": component, "status": status}
    digest = hashlib.sha256(json.dumps(seed, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:20]
    return f"scorecard-{digest}"


def evaluate_scorecard(report: dict[str, Any]) -> dict[str, Any]:
    contract_errors = validate_report(report)
    verification = verify(report)
    diagnosis = diagnose(report)
    component = str(report.get("identity", {}).get("component", "unknown"))
    report_digest = digest_json(report)

    invariants = verification.get("invariants", [])
    fail_count = sum(1 for item in invariants if item.get("status") == "fail")
    warn_count = sum(1 for item in invariants if item.get("status") == "warn")
    critical_count = sum(1 for item in invariants if item.get("severity") == "critical" and item.get("status") == "fail")

    policy_counts = report.get("policy", {}).get("policy_decisions", {}) if isinstance(report.get("policy"), dict) else {}
    lane_statuses = {lane.get("name", "unknown"): lane.get("status", "unknown") for lane in report.get("lanes", []) if isinstance(lane, dict)}
    replay_lag_events = sum(int(lane.get("journal", {}).get("replay_lag_events") or 0) for lane in report.get("lanes", []) if isinstance(lane, dict))
    disk_pressure = report.get("resources", {}).get("disk", {}).get("pressure", "unknown") if isinstance(report.get("resources"), dict) else "unknown"
    attested = bool(report.get("attestation", {}).get("signed")) if isinstance(report.get("attestation"), dict) else False

    gates = [
        {
            "id": "contract.valid",
            "status": "pass" if not contract_errors else "fail",
            "evidence": {"errors": contract_errors},
        },
        {
            "id": "diagnosis.not_unsafe",
            "status": "pass" if diagnosis.get("status") != "unsafe" else "fail",
            "evidence": {"diagnosis": diagnosis.get("status")},
        },
        {
            "id": "critical_invariants.none",
            "status": "pass" if critical_count == 0 else "fail",
            "evidence": {"critical_failures": critical_count},
        },
        {
            "id": "disk.not_critical",
            "status": "pass" if disk_pressure != "critical" else "fail",
            "evidence": {"pressure": disk_pressure},
        },
    ]

    score = 100
    score -= min(40, critical_count * 20)
    score -= min(30, fail_count * 10)
    score -= min(15, warn_count * 5)
    score -= 10 if replay_lag_events else 0
    score -= 10 if disk_pressure == "warning" else 0
    score -= 20 if disk_pressure == "critical" else 0
    score -= 5 if not attested else 0
    score = max(0, min(100, score))

    if any(gate["status"] == "fail" for gate in gates):
        status = "blocked"
    elif score >= 90:
        status = "ready"
    elif score >= 70:
        status = "watch"
    else:
        status = "degraded"

    dimensions = {
        "diagnosis": diagnosis,
        "contract_errors": contract_errors,
        "invariant_failures": fail_count,
        "invariant_warnings": warn_count,
        "critical_failures": critical_count,
        "lane_statuses": lane_statuses,
        "replay_lag_events": replay_lag_events,
        "disk_pressure": disk_pressure,
        "policy_counts": policy_counts,
        "attestation_signed": attested,
    }
    summary = f"{component} scorecard status={status} score={score} diagnosis={diagnosis.get('status', 'unknown')}"
    return Scorecard(
        scorecard_id=_scorecard_id(report_digest, component, status),
        component=component,
        status=status,
        score=score,
        report_digest=report_digest,
        summary=summary,
        dimensions=dimensions,
        gates=gates,
    ).as_dict()


def validate_scorecard(scorecard: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {"schema", "scorecard_id", "generated_at", "engine", "component", "status", "score", "report_digest", "summary", "dimensions", "gates"}
    missing = sorted(required - set(scorecard))
    if missing:
        errors.append(f"missing scorecard keys: {', '.join(missing)}")
    if scorecard.get("schema") != SCORECARD_SCHEMA:
        errors.append(f"unsupported scorecard schema: {scorecard.get('schema')!r}")
    if scorecard.get("status") not in {"ready", "watch", "degraded", "blocked"}:
        errors.append("status is invalid")
    score = scorecard.get("score")
    if not isinstance(score, int) or score < 0 or score > 100:
        errors.append("score must be an integer from 0 to 100")
    if not str(scorecard.get("report_digest", "")).startswith("sha256:"):
        errors.append("report_digest must start with sha256:")
    if not isinstance(scorecard.get("dimensions"), dict):
        errors.append("dimensions must be an object")
    if not isinstance(scorecard.get("gates"), list):
        errors.append("gates must be a list")
    return errors
