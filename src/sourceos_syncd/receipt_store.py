"""Persistent local store for SyncCycleReceipts.

Receipts are written as individual JSON files under a configurable directory.
The store also tracks the last successfully applied content view version so
the daemon can detect when a new version is available without re-querying
the state from an external source.

Layout:
  {store_root}/
    current-version        — plain-text file: current applied CV version
    receipts/
      {issuedAt}-{id}.json — one file per SyncCycleReceipt
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_STORE_ROOT = "/var/lib/sourceos-syncd"


class ReceiptStore:
    def __init__(self, root: str = DEFAULT_STORE_ROOT) -> None:
        self._root = Path(root)
        self._receipts_dir = self._root / "receipts"

    def ensure_dirs(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        self._receipts_dir.mkdir(parents=True, exist_ok=True)

    # ── version tracking ────────────────────────────────────────────────────

    @property
    def _version_file(self) -> Path:
        return self._root / "current-version"

    def read_current_version(self) -> str | None:
        if not self._version_file.exists():
            return None
        text = self._version_file.read_text(encoding="utf-8").strip()
        return text or None

    def write_current_version(self, version: str) -> None:
        self.ensure_dirs()
        self._version_file.write_text(version + "\n", encoding="utf-8")

    # ── receipt persistence ──────────────────────────────────────────────────

    def write_receipt(self, receipt: dict[str, Any]) -> Path:
        self.ensure_dirs()
        issued = receipt.get("issuedAt", "unknown").replace(":", "-").replace("T", "_")
        rid = receipt.get("id", "").split(":")[-1][:16]
        filename = f"{issued}-{rid}.json"
        path = self._receipts_dir / filename
        path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def list_receipts(self, limit: int = 20) -> list[dict[str, Any]]:
        if not self._receipts_dir.exists():
            return []
        files = sorted(self._receipts_dir.glob("*.json"), reverse=True)[:limit]
        receipts = []
        for f in files:
            try:
                receipts.append(json.loads(f.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                continue
        return receipts

    def last_receipt(self) -> dict[str, Any] | None:
        results = self.list_receipts(limit=1)
        return results[0] if results else None
