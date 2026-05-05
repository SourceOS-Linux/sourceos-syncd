from __future__ import annotations

import copy

from sourceos_syncd.reports import (
    REPAIR_SCHEMA,
    STATE_SCHEMA,
    repair_plan,
    snapshot,
    validate_repair_plan,
    validate_report,
    verify,
    with_fresh_diagnosis,
)


def test_snapshot_matches_state_integrity_contract() -> None:
    report = snapshot()

    assert report["schema"] == STATE_SCHEMA
    assert validate_report(report) == []
    assert report["identity"]["component"] == "sourceos-syncd"
    assert report["diagnosis"]["status"] in {"healthy", "degraded", "unsafe"}


def test_verify_fails_invalid_schema() -> None:
    report = snapshot()
    report["schema"] = "sourceos.invalid/v0"

    result = verify(report)

    assert result["status"] == "fail"
    assert any(invariant["id"] == "report.contract_valid" for invariant in result["invariants"])


def test_repair_plan_is_preview_only_and_valid() -> None:
    report = snapshot()
    plan = repair_plan(report)

    assert plan["schema"] == REPAIR_SCHEMA
    assert plan["status"] == "preview"
    assert plan["policy"]["destructive_actions_present"] is False
    assert validate_repair_plan(plan) == []
    assert all(step["destructive"] is False for step in plan["steps"])


def test_with_fresh_diagnosis_does_not_mutate_input_report() -> None:
    report = snapshot()
    original = copy.deepcopy(report)

    refreshed = with_fresh_diagnosis(report)

    assert report == original
    assert refreshed is not report
    assert refreshed["diagnosis"]["status"] in {"healthy", "degraded", "unsafe"}
