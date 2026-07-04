"""Tests for SyncDaemon and ReceiptStore."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sourceos_syncd.receipt_store import ReceiptStore
from sourceos_syncd.daemon import SyncDaemon
from sourceos_syncd.katello_client import ContentViewManifest


# ── ReceiptStore ──────────────────────────────────────────────────────────────


def _make_receipt(outcome: str = "applied", version: str = "1.0") -> dict:
    return {
        "id": f"urn:srcos:sync-receipt:test-{version}",
        "type": "SyncCycleReceipt",
        "specVersion": "0.1.0",
        "cycleId": "test-cycle",
        "engineId": "sourceos.sync.katello-content",
        "org": "SocioProphet",
        "contentView": "sourceos-builder-aarch64",
        "fromVersion": None,
        "toVersion": version,
        "lifecycleEnv": "dev",
        "locus": "local",
        "outcome": outcome,
        "steps": [],
        "issuedAt": "2026-06-16T00:00:00Z",
        "auditId": "urn:srcos:audit:test",
    }


def test_receipt_store_write_and_read():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ReceiptStore(root=tmpdir)
        receipt = _make_receipt(outcome="applied", version="1.0")
        path = store.write_receipt(receipt)
        assert path.exists()
        last = store.last_receipt()
        assert last is not None
        assert last["outcome"] == "applied"


def test_receipt_store_list_receipts():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ReceiptStore(root=tmpdir)
        for v in ["1.0", "1.1", "1.2"]:
            receipt = _make_receipt(version=v)
            receipt["issuedAt"] = f"2026-06-16T0{v.replace('.', ':')}:00Z"
            store.write_receipt(receipt)
        receipts = store.list_receipts(limit=10)
        assert len(receipts) == 3


def test_receipt_store_empty():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ReceiptStore(root=tmpdir)
        assert store.last_receipt() is None
        assert store.list_receipts() == []


def test_current_version_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ReceiptStore(root=tmpdir)
        assert store.read_current_version() is None
        store.write_current_version("2.3")
        assert store.read_current_version() == "2.3"


# ── SyncDaemon._poll_once ─────────────────────────────────────────────────────


def _make_daemon(tmpdir: str, current_version: str | None = None) -> SyncDaemon:
    daemon = SyncDaemon(
        katello_url="https://127.0.0.1:8443",
        katello_user="admin",
        katello_password="test",
        org="SocioProphet",
        content_view="sourceos-builder-aarch64",
        lifecycle_env="stable",
        locus="local",
        flake_ref="github:SociOS-Linux/source-os#builder-aarch64",
        poll_interval_s=1,
        store_root=tmpdir,
        verify_ssl=False,
    )
    if current_version:
        daemon._store.write_current_version(current_version)
    return daemon


def _manifest(version: str = "1.0") -> ContentViewManifest:
    return ContentViewManifest(
        org="SocioProphet",
        content_view="sourceos-builder-aarch64",
        version=version,
        lifecycle_env="stable",
        katello_url="https://127.0.0.1:8443",
        pulp_content_url="http://127.0.0.1:8101",
        nix_cache_url="http://127.0.0.1:8101",
    )


def test_poll_once_noop_when_current(tmp_path):
    daemon = _make_daemon(str(tmp_path), current_version="1.0")
    with patch.object(daemon._client, "get_latest_version", return_value=_manifest("1.0")):
        daemon._poll_once()
    # no receipt written when no-op
    assert daemon._store.last_receipt() is None


def test_poll_once_writes_receipt_on_apply(tmp_path):
    daemon = _make_daemon(str(tmp_path))
    with patch.object(daemon._client, "get_latest_version", return_value=_manifest("1.0")):
        with patch("sourceos_syncd.content_sync.subprocess.run") as mock_run:
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.stdout = ""
            mock_proc.stderr = ""
            mock_run.return_value = mock_proc
            import shutil as _shutil
            with patch("sourceos_syncd.content_sync.shutil.which", return_value="/usr/bin/nix"):
                daemon._poll_once()

    receipt = daemon._store.last_receipt()
    assert receipt is not None
    assert receipt["toVersion"] == "1.0"
    assert daemon._store.read_current_version() == "1.0"


def test_poll_once_denied_does_not_update_version(tmp_path):
    daemon = _make_daemon(str(tmp_path))
    # change locus to denied
    daemon._locus = "burst_cloud"
    with patch.object(daemon._client, "get_latest_version", return_value=_manifest("1.0")):
        daemon._poll_once()
    # receipt written, but version not updated
    receipt = daemon._store.last_receipt()
    assert receipt is not None
    assert receipt["outcome"] == "denied"
    assert daemon._store.read_current_version() is None


def test_poll_once_raises_on_failed(tmp_path):
    daemon = _make_daemon(str(tmp_path))
    fail_result = {
        "status": "failed",
        "receipt": _make_receipt(outcome="failed"),
    }
    with patch.object(daemon._client, "get_latest_version", return_value=_manifest("1.0")):
        with patch("sourceos_syncd.content_sync.ContentViewSyncer.execute", return_value=fail_result):
            with pytest.raises(RuntimeError, match="sync failed"):
                daemon._poll_once()
