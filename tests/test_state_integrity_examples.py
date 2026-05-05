from __future__ import annotations

import copy
import json
from pathlib import Path

from sourceos_syncd.reports import diagnose, repair_plan, snapshot, validate_repair_plan, validate_report, validate_shape, verify

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "health"
SCHEMAS = ROOT / "schemas"


def load_example(name: str):
    with open(EXAMPLES / name, "r", encoding="utf-8") as handle:
        return json.load(handle)


def test_schema_files_are_valid_json():
    for path in SCHEMAS.glob("*.schema.json"):
        with open(path, "r", encoding="utf-8") as handle:
            schema = json.load(handle)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["title"]


def test_runtime_snapshot_has_required_shape_and_contract():
    report = snapshot()
    assert validate_shape(report) == []
    assert validate_report(report) == []
    assert report["schema"] == "sourceos.state-integrity-report/v1alpha1"
    assert report["identity"]["component"] == "sourceos-syncd"


def test_healthy_example_diagnoses_as_healthy():
    report = load_example("healthy.snapshot.json")
    assert validate_report(report) == []
    assert diagnose(report)["status"] == "healthy"
    assert verify(report)["status"] == "pass"


def test_degraded_example_produces_safe_actions():
    report = load_example("degraded.snapshot.json")
    assert validate_report(report) == []
    diagnosis = diagnose(report)
    assert diagnosis["status"] in {"degraded", "unsafe"}
    assert "run_replay" in diagnosis["safe_actions"]
    assert diagnosis["blocked_actions"]


def test_contract_validation_catches_bad_flags():
    report = load_example("healthy.snapshot.json")
    bad = copy.deepcopy(report)
    bad["stores"][0]["flags_hex"] = "0xff"
    errors = validate_report(bad)
    assert any("flags_hex does not match flags_raw" in error for error in errors)


def test_contract_validation_catches_duplicate_lanes():
    report = load_example("healthy.snapshot.json")
    bad = copy.deepcopy(report)
    bad["lanes"].append(copy.deepcopy(bad["lanes"][0]))
    errors = validate_report(bad)
    assert any("duplicates lane" in error for error in errors)


def test_repair_plan_is_preview_only():
    report = load_example("degraded.snapshot.json")
    plan = repair_plan(report)
    assert validate_repair_plan(plan) == []
    assert plan["schema"] == "sourceos.repair-plan/v1alpha1"
    assert plan["status"] == "preview"
    assert plan["policy"]["destructive_actions_present"] is False
    assert all(step["destructive"] is False for step in plan["steps"])
