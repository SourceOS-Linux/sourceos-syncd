from __future__ import annotations

import json
from pathlib import Path

from sourceos_syncd.reports import validate_repair_plan, validate_report

SERVICE_EXAMPLES = Path("examples/service")


def load_json(name: str) -> dict:
    return json.loads((SERVICE_EXAMPLES / name).read_text(encoding="utf-8"))


def test_service_state_example_validates_as_state_integrity_report() -> None:
    report = load_json("statez.minimal.json")

    assert validate_report(report) == []


def test_service_repair_preview_example_validates_as_repair_plan() -> None:
    plan = load_json("repairz.preview.json")

    assert validate_repair_plan(plan) == []
    assert plan["status"] == "preview"
    assert plan["service"]["preview_only"] is True
    assert plan["policy"]["destructive_actions_present"] is False


def test_service_json_examples_have_expected_shapes() -> None:
    assert load_json("healthz.json")["live"] is True
    assert load_json("readyz.healthy.json")["ready"] is True
    assert load_json("readyz.uninitialized.json")["ready"] is False
    assert load_json("events.json")["events"][0]["event_id"] == "evt-00000001"
    assert load_json("event.evt-00000001.json")["event_id"] == "evt-00000001"
    assert load_json("event-explain.evt-00000001.json")["event_id"] == "evt-00000001"


def test_service_metrics_example_names_core_series() -> None:
    metrics = (SERVICE_EXAMPLES / "metrics.txt").read_text(encoding="utf-8")

    assert "sourceos_syncd_ready" in metrics
    assert "sourceos_syncd_initialized" in metrics
    assert "sourceos_syncd_replay_lag_events" in metrics
    assert "sourceos_syncd_corrupted_objects" in metrics
    assert "sourceos_syncd_ready_http_code" in metrics
