#!/usr/bin/env python3
"""Validate JSON syntax for SourceOS schema and example files."""

from __future__ import annotations

import json
import pathlib
import sys


def main() -> int:
    failed = False
    for root in (pathlib.Path("schemas"), pathlib.Path("examples")):
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.json")):
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:  # pragma: no cover - diagnostic path
                print(f"{path}: invalid JSON: {exc}", file=sys.stderr)
                failed = True
    if failed:
        return 1
    print("JSON syntax validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
