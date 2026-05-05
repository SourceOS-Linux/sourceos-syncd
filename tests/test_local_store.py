from __future__ import annotations

from pathlib import Path

import pytest

from sourceos_syncd.local_store import DURABLE_DIRS, REBUILDABLE_DIRS, DISPOSABLE_DIRS, LocalStateStore
from sourceos_syncd.reports import validate_report
from sourceos_syncd.store_reports import append_store_event, init_store, snapshot_from_store


def test_uninitialized_store_read_does_not_create_files(tmp_path: Path) -> None:
    root = tmp_path / "state"
    store = LocalStateStore(root)

    manifest = store.read_manifest()
    summary = store.summarize()

    assert manifest["initialized"] is False
    assert summary["local_state"]["initialized"] is False
    assert not root.exists()


def test_store_init_creates_classified_state_directories(tmp_path: Path) -> None:
    root = tmp_path / "state"
    store = LocalStateStore(root)

    manifest = store.init()

    assert manifest["schema"] == "sourceos.local-state-store/v1alpha1"
    assert manifest["initialized"] is True
    assert (root / "manifest.json").exists()
    assert (root / "journal.jsonl").exists()
    for directory in (*DURABLE_DIRS, *REBUILDABLE_DIRS, *DISPOSABLE_DIRS):
        assert (root / directory).is_dir()


def test_event_append_round_trips_and_updates_summary(tmp_path: Path) -> None:
    root = tmp_path / "state"
    store = LocalStateStore(root)
    store.init()

    event = store.append_event("add", lane="normal", object_id="object:alpha", producer="pytest", payload={"name": "alpha"})
    events = store.iter_events()
    summary = store.summarize()

    assert event["event_id"] == "evt-00000001"
    assert events == [event]
    assert summary["pipeline"]["add"]["journaled"] == 1
    assert summary["pipeline"]["add"]["applied"] == 1
    assert summary["lanes"][0]["journal"]["segment_count"] == 1
    assert summary["local_state"]["journal_present"] is True


def test_event_append_requires_initialized_store(tmp_path: Path) -> None:
    store = LocalStateStore(tmp_path / "state")

    with pytest.raises(FileNotFoundError):
        store.append_event("add")


def test_store_report_adapter_initializes_for_record_command_compatibility(tmp_path: Path) -> None:
    manifest = init_store(tmp_path)
    event = append_store_event(tmp_path, "add", "normal", "obj-1", "test", {"path": "README.md"})

    assert manifest["initialized"] is True
    assert event["event_id"] == "evt-00000001"


def test_registry_record_round_trip_and_counts(tmp_path: Path) -> None:
    root = tmp_path / "state"
    store = LocalStateStore(root)
    store.init()

    actor = store.put_record(
        "actors",
        "actor:agent-one",
        {
            "actor_id": "actor:agent-one",
            "actor_type": "agent",
            "display_name": "Agent One",
            "capabilities": ["read", "write"],
        },
    )

    assert actor["record_id"] == "actor:agent-one"
    assert actor["schema"] == "sourceos.actor-record/v1alpha1"
    assert store.get_record("actors", "actor:agent-one")["display_name"] == "Agent One"
    assert [record["actor_id"] for record in store.list_records("actors")] == ["actor:agent-one"]
    assert store.summarize()["local_state"]["registry_counts"]["actors"] == 1


def test_registry_rejects_unknown_kind_and_empty_id(tmp_path: Path) -> None:
    store = LocalStateStore(tmp_path / "state")
    store.init()

    with pytest.raises(ValueError):
        store.put_record("unknown", "id", {})
    with pytest.raises(ValueError):
        store.put_record("actors", "   ", {})


def test_store_backed_snapshot_validates(tmp_path: Path) -> None:
    root = tmp_path / "state"
    store = LocalStateStore(root)
    store.init()
    store.append_event("add", object_id="object:alpha", producer="pytest")
    store.put_record("objects", "object:alpha", {"object_id": "object:alpha", "object_type": "file"})

    report = snapshot_from_store(root)

    assert validate_report(report) == []
    assert report["identity"]["store_root"] == str(root.resolve())
    assert report["local_state"]["initialized"] is True
    assert report["local_state"]["registry_counts"]["objects"] == 1
    assert report["diagnosis"]["local_state"]["registry_counts"]["objects"] == 1
    assert report["diagnosis"]["top_producers"][0]["producer"] == "pytest"


def test_uninitialized_store_snapshot_is_contract_valid_and_non_mutating(tmp_path: Path) -> None:
    root = tmp_path / "missing-state"

    report = snapshot_from_store(root)

    assert validate_report(report) == []
    assert report["local_state"]["initialized"] is False
    assert report["diagnosis"]["local_state"]["initialized"] is False
    assert any("not initialized" in item for item in report["collection"]["errors"])
    assert not root.exists()
