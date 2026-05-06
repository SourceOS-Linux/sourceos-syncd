#!/usr/bin/env python3
"""Validate SourceOS canonical event fixtures.

Default behavior:
- valid fixtures under examples/events/*.json must pass;
- invalid fixtures under examples/events/invalid/*.json must fail.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = ROOT / "schemas" / "sourceos.event.v0.1.schema.json"
DEFAULT_VALID_GLOB = "examples/events/*.json"
DEFAULT_INVALID_GLOB = "examples/events/invalid/*.json"


def load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def iter_paths(pattern: str) -> list[Path]:
    return sorted(path for path in ROOT.glob(pattern) if path.is_file())


def validate_files(validator: Draft202012Validator, paths: Iterable[Path], expect_fail: bool) -> int:
    failures = 0
    for path in paths:
        instance = load_json(path)
        errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.path))
        if expect_fail:
            if errors:
                print(f"PASS expected failure: {path.relative_to(ROOT)}")
            else:
                failures += 1
                print(f"FAIL expected invalid fixture to fail: {path.relative_to(ROOT)}")
        else:
            if errors:
                failures += 1
                print(f"FAIL invalid valid-fixture: {path.relative_to(ROOT)}")
                for error in errors:
                    location = "/".join(str(part) for part in error.path) or "<root>"
                    print(f"  - {location}: {error.message}")
            else:
                print(f"PASS valid fixture: {path.relative_to(ROOT)}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA), help="Path to JSON Schema file")
    parser.add_argument("--valid-glob", default=DEFAULT_VALID_GLOB, help="Repository-root glob for fixtures expected to pass")
    parser.add_argument("--invalid-glob", default=DEFAULT_INVALID_GLOB, help="Repository-root glob for fixtures expected to fail")
    args = parser.parse_args()

    schema_path = Path(args.schema)
    if not schema_path.is_absolute():
        schema_path = ROOT / schema_path

    schema = load_json(schema_path)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    Draft202012Validator.check_schema(schema)

    valid_paths = iter_paths(args.valid_glob)
    invalid_paths = iter_paths(args.invalid_glob)

    if not valid_paths:
        print(f"FAIL no valid fixtures matched {args.valid_glob}")
        return 1
    if not invalid_paths:
        print(f"FAIL no invalid fixtures matched {args.invalid_glob}")
        return 1

    failures = 0
    failures += validate_files(validator, valid_paths, expect_fail=False)
    failures += validate_files(validator, invalid_paths, expect_fail=True)

    if failures:
        print(f"Validation completed with {failures} failure(s).")
        return 1

    print("Validation completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
