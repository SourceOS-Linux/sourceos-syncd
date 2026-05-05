from __future__ import annotations

from sourceos_syncd.local_store import LocalStateStore
from sourceos_syncd.reports import validate_report
from sourceos_syncd.store_reports import append_store_event, init_store, snapshot_from_store


def test_local_store_initializes_manifest_and_journal(tmp_path):
    manifest = init_store(tmp_path)
    assert manifest["schema"] == "sourceos.local-state-store/v1alpha1"
    assert (tmp_path / "manifest.json").exists()
    assert (tmp_path / "journal.jsonl").exists()
    assert (tmp_path / "objects").is_dir()
    assert (tmp_path / "checkpoints").is_dir()


def test_uninitialized_store_snapshot_is_contract_valid(tmp_path):
    report = snapshot_from_store(tmp_path)
    assert report["identity"]["store_root"] == str(tmp_path.resolve())
    assert report["diagnosis"]["local_state"]["initialized"] is False
    assert validate_report(report) == []


def test_local_store_records_events_and_summarizes(tmp_path):
    init_store(tmp_path)
    append_store_event(tmp_path, "add", "normal", "obj-1", "test", {"path": "README.md"})
    append_store_event(tmp_path, "update", "priority", "obj-1", "test", {"field": "title"})
    append_store_event(tmp_path, "delete", "normal", "obj-1", "test", {"reason": "test"})

    summary = LocalStateStore(tmp_path).summarize()
    assert summary["pipeline"]["add"]["journaled"] == 1
    assert summary["pipeline"]["update"]["journaled"] == 1
    assert summary["pipeline"]["delete"]["journaled"] == 1
    assert summary["top_producers"][0]["producer"] == "test"
    assert summary["stores"][0]["manifest_present"] is True
    assert summary["local_state"]["registry_counts"]["objects"] == 0


def test_store_backed_snapshot_validates(tmp_path):
    init_store(tmp_path)
    append_store_event(tmp_path, "add", "normal", "obj-1", "test", {"path": "README.md"})
    report = snapshot_from_store(tmp_path)
    assert report["identity"]["store_root"] == str(tmp_path.resolve())
    assert report["diagnosis"]["top_producers"][0]["producer"] == "test"
    assert validate_report(report) == []
