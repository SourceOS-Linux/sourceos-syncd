from __future__ import annotations

import copy

from sourceos_syncd.reports import snapshot, validate_report
from sourceos_syncd.trust import TrustRequest, evaluate_trust, validate_trust_decision


def test_trust_allows_healthy_normal_lane():
    report = snapshot()
    assert validate_report(report) == []
    decision = evaluate_trust(report, TrustRequest(subject="agentplane", action="read", lane="normal"))
    assert decision["status"] == "allowed"
    assert decision["reason"] == "state_integrity_allows_agent_action"
    assert validate_trust_decision(decision) == []


def test_trust_blocks_missing_lane():
    report = snapshot()
    decision = evaluate_trust(report, TrustRequest(subject="agentplane", action="read", lane="secure"))
    assert decision["status"] == "blocked"
    assert decision["reason"] == "requested_lane_missing"


def test_trust_blocks_when_attestation_required_but_missing():
    report = snapshot()
    decision = evaluate_trust(report, TrustRequest(subject="agentplane", action="read", lane="normal", require_attestation=True))
    assert decision["status"] == "blocked"
    assert decision["reason"] == "required_attestation_missing"


def test_trust_allows_degraded_only_when_explicitly_allowed():
    report = snapshot()
    degraded = copy.deepcopy(report)
    degraded["runtime"]["last_heartbeat_at"] = "2020-01-01T00:00:00Z"

    blocked = evaluate_trust(degraded, TrustRequest(subject="agentplane", action="read", lane="normal"))
    assert blocked["status"] == "blocked"
    assert blocked["reason"] == "degraded_mode_requires_explicit_allowance"

    allowed = evaluate_trust(degraded, TrustRequest(subject="agentplane", action="read", lane="normal", allow_degraded=True))
    assert allowed["status"] == "degraded_allowed"
    assert allowed["reason"] == "degraded_mode_explicitly_allowed"


def test_trust_validation_catches_bad_digest():
    report = snapshot()
    decision = evaluate_trust(report, TrustRequest(subject="agentplane", action="read", lane="normal"))
    decision["report_digest"] = "bad"
    errors = validate_trust_decision(decision)
    assert any("report_digest" in error for error in errors)
