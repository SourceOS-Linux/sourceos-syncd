"""Adapters that project LocalStateStore data into State Integrity Reports."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from .local_store import LocalStateStore
from .policy import POLICY_ENGINE, decision_counts, evaluate_report_policy, policy_summary
from .reports import controls_for, diagnose, snapshot, verify


def snapshot_from_store(root: str | Path) -> dict[str, Any]:
    """Build a State Integrity Report from a filesystem-backed local store."""
    store = LocalStateStore(root)
    summary = store.summarize()
    report = snapshot()
    report["stores"] = summary["stores"]
    report["lanes"] = summary["lanes"]
    report["pipeline"] = summary["pipeline"]
    report["local_state"] = copy.deepcopy(summary["local_state"])
    report["collection"]["status"] = "partial"
    if not summary["local_state"]["initialized"]:
        report["collection"]["errors"] = sorted(set(report["collection"].get("errors", []) + ["local store is not initialized; run store init first"]))
    report["collection"]["unavailable_fields"] = sorted(set(report["collection"].get("unavailable_fields", []) + ["memory.total_gb", "identity.boot_id"]))
    report["identity"]["store_root"] = str(Path(root).expanduser().resolve())

    decisions = evaluate_report_policy(report["lanes"], subject="sourceos-syncd")
    report["policy"]["policy_engine"] = POLICY_ENGINE
    report["policy"]["policy_version"] = "v0.1.0-local"
    report["policy"]["policy_decisions"] = decision_counts(decisions)

    report["diagnosis"] = diagnose(report)
    report["diagnosis"]["local_state"] = copy.deepcopy(summary["local_state"])
    report["diagnosis"]["top_producers"] = copy.deepcopy(summary.get("top_producers", []))
    report["diagnosis"]["policy"] = policy_summary(decisions)
    report["invariants"] = verify(report)["invariants"]
    report["controls"] = controls_for(report)
    return report


def init_store(root: str | Path) -> dict[str, Any]:
    return LocalStateStore(root).init()


def append_store_event(root: str | Path, event_type: str, lane: str, object_id: str | None, producer: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    store = LocalStateStore(root)
    store.init()
    return store.append_event(event_type=event_type, lane=lane, object_id=object_id, producer=producer, payload=payload)


def put_store_record(root: str | Path, kind: str, record_id: str, record: dict[str, Any]) -> dict[str, Any]:
    store = LocalStateStore(root)
    return store.put_record(kind=kind, record_id=record_id, record=record)


def get_store_record(root: str | Path, kind: str, record_id: str) -> dict[str, Any]:
    return LocalStateStore(root).get_record(kind=kind, record_id=record_id)


def list_store_records(root: str | Path, kind: str) -> list[dict[str, Any]]:
    return LocalStateStore(root).list_records(kind=kind)
