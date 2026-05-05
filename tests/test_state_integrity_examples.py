from __future__ import annotations

import json
from pathlib import Path

from sourceos_syncd.reports import diagnose, repair_plan, snapshot, validate_shape, verify

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "health"


def load_example(name: str):
    with open(EXAMPLES / name, "r", encoding="utf-8") as handle:
        return json.load(handle)


def test_runtime_snapshot_has_required_shape():
    report = snapshot()
    assert validate_shape(report) == []
    assert report["schema"] == "sourceos.state-integrity-report/v1alpha1"
    assert report["identity"]["component"] == "sourceos-syncd"


def test_healthy_example_diagnoses_as_healthy():
    report = load_example("healthy.snapshot.json")
    assert validate_shape(report) == []
    assert diagnose(report)["status"] == "healthy"
    assert verify(report)["status"] == "pass"


def test_degraded_example_produces_safe_actions():
    report = load_example("degraded.snapshot.json")
    diagnosis = diagnose(report)
    assert diagnosis["status"] in {"degraded", "unsafe"}
    assert "run_replay" in diagnosis["safe_actions"]
    assert diagnosis["blocked_actions"]


def test_repair_plan_is_preview_only():
    report = load_example("degraded.snapshot.json")
    plan = repair_plan(report)
    assert plan["schema"] == "sourceos.repair-plan/v1alpha1"
    assert plan["status"] == "preview"
    assert plan["policy"]["destructive_actions_present"] is False
    assert all(step["destructive"] is False for step in plan["steps"])
