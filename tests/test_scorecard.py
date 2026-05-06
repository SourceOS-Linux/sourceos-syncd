from __future__ import annotations

from sourceos_syncd.reports import snapshot
from sourceos_syncd.scorecard import evaluate_scorecard, validate_scorecard


def test_scorecard_ready_for_healthy_snapshot():
    report = snapshot()
    scorecard = evaluate_scorecard(report)
    assert scorecard["schema"] == "sourceos.delivery-scorecard/v1alpha1"
    assert scorecard["component"] == "sourceos-syncd"
    assert scorecard["status"] in {"ready", "watch"}
    assert 0 <= scorecard["score"] <= 100
    assert validate_scorecard(scorecard) == []


def test_scorecard_blocks_contract_errors():
    report = snapshot()
    del report["identity"]["node_id_hash"]
    scorecard = evaluate_scorecard(report)
    assert scorecard["status"] == "blocked"
    assert any(gate["id"] == "contract.valid" and gate["status"] == "fail" for gate in scorecard["gates"])


def test_scorecard_warns_on_unattested_state():
    report = snapshot()
    scorecard = evaluate_scorecard(report)
    assert scorecard["dimensions"]["attestation_signed"] is False
    assert scorecard["score"] <= 95


def test_scorecard_validation_catches_bad_score():
    report = snapshot()
    scorecard = evaluate_scorecard(report)
    scorecard["score"] = 101
    errors = validate_scorecard(scorecard)
    assert any("score" in error for error in errors)
