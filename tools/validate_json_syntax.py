#!/usr/bin/env python3
"""Validate JSON syntax for repository schemas and examples."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    failed = False
    for root_name in ("schemas", "examples"):
        root = ROOT / root_name
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.json")):
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:  # noqa: BLE001 - syntax validator should report any parse/read failure.
                rel = path.relative_to(ROOT)
                print(f"{rel}: invalid JSON: {exc}", file=sys.stderr)
                failed = True
    if failed:
        return 1
    print("JSON syntax validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
