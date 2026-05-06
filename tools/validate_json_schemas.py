#!/usr/bin/env python3
"""Validate SourceOS schemas and golden examples with jsonschema.

This is the formal validator for CI. The bootstrap validator remains useful in
minimal environments, but this script checks Draft 2020-12 schema validity and
validates known examples against their canonical schemas.
"""

from __future__ import annotations

import json
import pathlib
import sys
from dataclasses import dataclass
from typing import Any

try:
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import SchemaError, ValidationError
except Exception as exc:  # pragma: no cover - exercised in environments without deps
    print(
        "Missing dependency: jsonschema. Install with `python3 -m pip install -r requirements-dev.txt`.",
        file=sys.stderr,
    )
    raise SystemExit(2) from exc

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
EXAMPLES = ROOT / "examples"


@dataclass(frozen=True)
class ValidationTarget:
    schema_path: pathlib.Path
    example_glob: str


TARGETS = [
    ValidationTarget(SCHEMAS / "sourceos-event.schema.json", "events/*.json"),
    ValidationTarget(SCHEMAS / "sourceos-service.schema.json", "services/*.json"),
    ValidationTarget(SCHEMAS / "sourceos-capability.schema.json", "capabilities/*.json"),
    ValidationTarget(SCHEMAS / "sourceos-launch-manifest.schema.json", "launch/*.json"),
    ValidationTarget(SCHEMAS / "sourceos-incident.schema.json", "incidents/*.json"),
    ValidationTarget(SCHEMAS / "sourceos.state-integrity-report.v1alpha1.schema.json", "health/*.snapshot.json"),
    ValidationTarget(SCHEMAS / "sourceos.repair-plan.v1alpha1.schema.json", "health/*repair-plan*.json"),
]


def load_json(path: pathlib.Path) -> Any:
    try:
        return json.loads(path.read_text())
    except Exception as exc:
        raise RuntimeError(f"{path}: invalid JSON: {exc}") from exc


def check_all_schemas() -> list[str]:
    errors: list[str] = []
    for path in sorted(SCHEMAS.glob("*.json")):
        try:
            Draft202012Validator.check_schema(load_json(path))
        except (RuntimeError, SchemaError) as exc:
            errors.append(f"{path}: invalid schema: {exc}")
    return errors


def format_validation_error(path: pathlib.Path, exc: ValidationError) -> str:
    location = ".".join(str(part) for part in exc.absolute_path)
    if not location:
        location = "<root>"
    return f"{path}: validation failed at {location}: {exc.message}"


def validate_examples() -> list[str]:
    errors: list[str] = []
    for target in TARGETS:
        if not target.schema_path.exists():
            errors.append(f"missing schema: {target.schema_path}")
            continue

        try:
            schema = load_json(target.schema_path)
        except RuntimeError as exc:
            errors.append(str(exc))
            continue

        validator = Draft202012Validator(schema)
        examples = sorted(EXAMPLES.glob(target.example_glob))
        if not examples:
            errors.append(f"{target.schema_path}: no examples matched {target.example_glob}")
            continue

        for example_path in examples:
            try:
                instance = load_json(example_path)
                validator.validate(instance)
            except RuntimeError as exc:
                errors.append(str(exc))
            except ValidationError as exc:
                errors.append(format_validation_error(example_path, exc))
    return errors


def main() -> int:
    errors = check_all_schemas()
    errors.extend(validate_examples())

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print("SourceOS JSON Schemas and examples validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
