from __future__ import annotations

import pytest

from sourceos_syncd.policy import (
    PolicyRequest,
    decision_counts,
    evaluate_policy,
    evaluate_report_policy,
    validate_decision_boundary,
)
from sourceos_syncd.store_reports import init_store, snapshot_from_store


def test_secure_lane_agent_access_is_denied():
    decision = evaluate_policy(PolicyRequest(action="agent_access", lane="secure"))
    assert decision.status == "denied"
    assert decision.reason == "secure_lane_requires_explicit_grant"
    payload = decision.as_dict()
    assert payload["decision_boundary"]["decision_scope"] == "policy-only"
    assert payload["decision_boundary"]["runtime_effect_performed"] is False
    assert payload["decision_boundary"]["authority_mutation_performed"] is False


def test_secure_lane_indexing_is_redacted():
    decision = evaluate_policy(PolicyRequest(action="index", lane="secure"))
    assert decision.status == "redacted"
    assert decision.reason == "secure_lane_indexing_requires_redaction"


def test_unknown_action_is_deferred():
    decision = evaluate_policy(PolicyRequest(action="unknown", lane="normal"))
    assert decision.status == "deferred"
    assert decision.reason == "unknown_action"


def test_policy_decision_rejects_collapsed_runtime_effect():
    decision = evaluate_policy(PolicyRequest(action="replicate", lane="normal")).as_dict()
    decision["decision_boundary"]["runtime_effect_performed"] = True
    with pytest.raises(ValueError, match="runtime_effect_performed"):
        validate_decision_boundary(decision)


def test_policy_decision_rejects_collapsed_authority_mutation():
    decision = evaluate_policy(PolicyRequest(action="agent_access", lane="secure")).as_dict()
    decision["decision_boundary"]["authority_mutation_performed"] = True
    with pytest.raises(ValueError, match="authority_mutation_performed"):
        validate_decision_boundary(decision)


def test_report_policy_counts_include_all_statuses():
    lanes = [{"name": "normal"}, {"name": "secure"}, {"name": "repair"}, {"name": "ephemeral"}]
    decisions = evaluate_report_policy(lanes)
    counts = decision_counts(decisions)
    assert counts["allowed"] > 0
    assert counts["denied"] > 0
    assert counts["redacted"] > 0
    assert counts["deferred"] > 0
    for decision in decisions:
        assert decision["decision_boundary"]["decision_scope"] == "policy-only"
        assert decision["decision_boundary"]["state_repair_performed"] is False
        assert decision["decision_boundary"]["ledger_write_performed"] is False


def test_store_backed_snapshot_includes_policy_summary(tmp_path):
    init_store(tmp_path)
    report = snapshot_from_store(tmp_path)
    assert report["policy"]["policy_engine"] == "policy-fabric-local-stub"
    assert report["policy"]["policy_version"] == "v0.1.0-local-stub"
    assert report["diagnosis"]["policy"]["engine"] == "policy-fabric-local-stub"
    assert report["diagnosis"]["policy"]["counts"]["allowed"] > 0
    sample = report["diagnosis"]["policy"]["sample"]
    assert sample
    assert sample[0]["decision_boundary"]["decision_scope"] == "policy-only"
