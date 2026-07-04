from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from sourceos_syncd.cli import main
from sourceos_syncd.receipt_store import ReceiptStore

RECENT_ISO = "2026-06-16T12:00:00+00:00"


def _write_receipt(store: ReceiptStore, outcome: str, issued_at: str = RECENT_ISO) -> None:
    store.write_receipt({
        "id": "receipt:test-abc",
        "issuedAt": issued_at,
        "outcome": outcome,
        "version": "1.2",
    })


def _run(args: list[str]) -> tuple[int, dict]:
    import io, sys
    buf = io.StringIO()
    with patch("sys.stdout", buf):
        rc = main(args)
    return rc, json.loads(buf.getvalue())


# ── empty store ──────────────────────────────────────────────────────────────


def test_status_empty_store_no_daemon(tmp_path: Path) -> None:
    with patch("subprocess.run", side_effect=FileNotFoundError):
        rc, out = _run(["sync", "status", "--store-root", str(tmp_path), "--compact"])

    assert out["daemon"] == "unknown"
    assert out["currentVersion"] is None
    assert out["lastReceipt"] is None
    assert out["storeReceipts"] == 0
    # daemon not active → not healthy
    assert out["healthy"] is False
    assert rc == 1


# ── daemon active, receipt applied ──────────────────────────────────────────


def test_status_healthy(tmp_path: Path) -> None:
    store = ReceiptStore(root=str(tmp_path))
    _write_receipt(store, "applied")
    store.write_current_version("1.2")

    with patch("subprocess.run") as mock_sp:
        mock_sp.return_value.stdout = "active\n"
        mock_sp.return_value.returncode = 0
        rc, out = _run(["sync", "status", "--store-root", str(tmp_path), "--compact"])

    assert out["daemon"] == "active"
    assert out["currentVersion"] == "1.2"
    assert out["lastReceipt"]["outcome"] == "applied"
    assert out["storeReceipts"] == 1
    assert out["healthy"] is True
    assert rc == 0


# ── outcome variants ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("outcome", ["dry_run", "planned", "no_change"])
def test_status_healthy_for_non_applied_good_outcomes(outcome: str, tmp_path: Path) -> None:
    store = ReceiptStore(root=str(tmp_path))
    _write_receipt(store, outcome)

    with patch("subprocess.run") as mock_sp:
        mock_sp.return_value.stdout = "active\n"
        mock_sp.return_value.returncode = 0
        rc, out = _run(["sync", "status", "--store-root", str(tmp_path), "--compact"])

    assert out["healthy"] is True
    assert rc == 0


def test_status_unhealthy_on_failed_outcome(tmp_path: Path) -> None:
    store = ReceiptStore(root=str(tmp_path))
    _write_receipt(store, "failed")

    with patch("subprocess.run") as mock_sp:
        mock_sp.return_value.stdout = "active\n"
        mock_sp.return_value.returncode = 0
        rc, out = _run(["sync", "status", "--store-root", str(tmp_path), "--compact"])

    assert out["healthy"] is False
    assert rc == 1


def test_status_unhealthy_when_daemon_inactive(tmp_path: Path) -> None:
    store = ReceiptStore(root=str(tmp_path))
    _write_receipt(store, "applied")

    with patch("subprocess.run") as mock_sp:
        mock_sp.return_value.stdout = "inactive\n"
        mock_sp.return_value.returncode = 3
        rc, out = _run(["sync", "status", "--store-root", str(tmp_path), "--compact"])

    assert out["daemon"] == "inactive"
    assert out["healthy"] is False
    assert rc == 1


# ── last receipt summary fields ───────────────────────────────────────────────


def test_status_receipt_age_seconds_is_non_negative(tmp_path: Path) -> None:
    store = ReceiptStore(root=str(tmp_path))
    _write_receipt(store, "applied", issued_at=RECENT_ISO)

    with patch("subprocess.run") as mock_sp:
        mock_sp.return_value.stdout = "active\n"
        _, out = _run(["sync", "status", "--store-root", str(tmp_path), "--compact"])

    age = out["lastReceipt"]["ageSeconds"]
    assert isinstance(age, int)
    assert age >= 0


def test_status_receipt_bad_timestamp_does_not_crash(tmp_path: Path) -> None:
    store = ReceiptStore(root=str(tmp_path))
    store.write_receipt({"id": "receipt:x", "issuedAt": "not-a-date", "outcome": "applied"})

    with patch("subprocess.run") as mock_sp:
        mock_sp.return_value.stdout = "active\n"
        rc, out = _run(["sync", "status", "--store-root", str(tmp_path), "--compact"])

    assert out["lastReceipt"]["ageSeconds"] is None
    assert out["lastReceipt"]["outcome"] == "applied"


# ── multiple receipts ─────────────────────────────────────────────────────────


def test_status_store_receipts_counts_all(tmp_path: Path) -> None:
    store = ReceiptStore(root=str(tmp_path))
    for i in range(5):
        store.write_receipt({
            "id": f"receipt:test-{i:04d}",
            "issuedAt": f"2026-06-16T12:0{i}:00+00:00",
            "outcome": "applied",
        })

    with patch("subprocess.run") as mock_sp:
        mock_sp.return_value.stdout = "active\n"
        _, out = _run(["sync", "status", "--store-root", str(tmp_path), "--compact"])

    assert out["storeReceipts"] == 5


# ── compact vs pretty output ─────────────────────────────────────────────────


def test_status_pretty_output_is_indented(tmp_path: Path) -> None:
    import io, sys
    buf = io.StringIO()
    with patch("subprocess.run", side_effect=FileNotFoundError):
        with patch("sys.stdout", buf):
            main(["sync", "status", "--store-root", str(tmp_path)])
    raw = buf.getvalue()
    # pretty JSON has newlines inside the object
    assert "\n" in raw


def test_status_compact_output_is_single_line(tmp_path: Path) -> None:
    import io, sys
    buf = io.StringIO()
    with patch("subprocess.run", side_effect=FileNotFoundError):
        with patch("sys.stdout", buf):
            main(["sync", "status", "--store-root", str(tmp_path), "--compact"])
    raw = buf.getvalue().strip()
    assert "\n" not in raw
