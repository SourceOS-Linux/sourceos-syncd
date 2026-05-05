#!/usr/bin/env python3
"""Validate SourceOS control-plane examples with standard-library checks.

This is intentionally not a full JSON Schema validator. It enforces the
minimum invariants needed in tiny bootstrap environments before a formal
schema validator is available in CI.
"""

from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]

EVENT_ENUMS = {
    "severity": {"trace", "debug", "info", "notice", "warning", "error", "critical"},
    "outcome": {
        "allowed",
        "blocked_expected",
        "blocked_unexpected",
        "blocked_attack_like",
        "degraded",
        "failed",
        "repaired",
        "observed",
    },
    "privacy_tier": {"public_summary", "user_private", "admin_forensic", "sealed_secret"},
}

REQUIRED_EVENT_KEYS = {
    "schema_version",
    "event_id",
    "event_class",
    "lane",
    "severity",
    "outcome",
    "created_at",
    "host",
    "actor",
    "causality",
    "subject",
    "privacy",
    "operator_narrative",
    "sync",
}

REQUIRED_SERVICE_KEYS = {
    "schema_version",
    "service_id",
    "display_name",
    "owner",
    "authority_domain",
    "lifecycle",
    "capabilities",
    "data_classes",
    "launch_triggers",
    "resource_budget",
    "observability",
}


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        raise SystemExit(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"{path}: expected top-level JSON object")
    return data


def require_keys(path: pathlib.Path, obj: dict[str, Any], keys: set[str]) -> list[str]:
    return [f"{path}: missing required key {key!r}" for key in sorted(keys - set(obj))]


def validate_event(path: pathlib.Path) -> list[str]:
    obj = load_json(path)
    errors = require_keys(path, obj, REQUIRED_EVENT_KEYS)

    if obj.get("schema_version") != "sourceos.event.v0.1":
        errors.append(f"{path}: schema_version must be sourceos.event.v0.1")

    if obj.get("severity") not in EVENT_ENUMS["severity"]:
        errors.append(f"{path}: invalid severity {obj.get('severity')!r}")

    if obj.get("outcome") not in EVENT_ENUMS["outcome"]:
        errors.append(f"{path}: invalid outcome {obj.get('outcome')!r}")

    privacy = obj.get("privacy") or {}
    if privacy.get("tier") not in EVENT_ENUMS["privacy_tier"]:
        errors.append(f"{path}: invalid privacy.tier {privacy.get('tier')!r}")

    causality = obj.get("causality") or {}
    if not causality.get("root_event_id") or not causality.get("trace_id"):
        errors.append(f"{path}: causality.root_event_id and trace_id are required")

    narrative = obj.get("operator_narrative") or {}
    for key in ("summary", "risk", "why", "next_action"):
        if not narrative.get(key):
            errors.append(f"{path}: operator_narrative.{key} is required")

    if obj.get("outcome") == "blocked_expected" and obj.get("severity") not in {"trace", "debug", "info", "notice"}:
        errors.append(f"{path}: blocked_expected should not be warning/error by default")

    return errors


def validate_service(path: pathlib.Path) -> list[str]:
    obj = load_json(path)
    errors = require_keys(path, obj, REQUIRED_SERVICE_KEYS)

    if obj.get("schema_version") != "sourceos.service.v0.1":
        errors.append(f"{path}: schema_version must be sourceos.service.v0.1")

    caps = obj.get("capabilities") or {}
    for key in ("required", "optional", "denied"):
        if not isinstance(caps.get(key), list):
            errors.append(f"{path}: capabilities.{key} must be a list")

    return errors


def validate_prefix(path: pathlib.Path, expected_version: str) -> list[str]:
    obj = load_json(path)
    if obj.get("schema_version") != expected_version:
        return [f"{path}: schema_version must be {expected_version}"]
    return []


def main() -> int:
    errors: list[str] = []

    for path in sorted((ROOT / "examples" / "events").glob("*.json")):
        errors.extend(validate_event(path))

    for path in sorted((ROOT / "examples" / "services").glob("*.json")):
        errors.extend(validate_service(path))

    versioned_dirs = {
        ROOT / "examples" / "capabilities": "sourceos.capability.v0.1",
        ROOT / "examples" / "launch": "sourceos.launch_manifest.v0.1",
        ROOT / "examples" / "incidents": "sourceos.incident.v0.1",
    }
    for directory, version in versioned_dirs.items():
        for path in sorted(directory.glob("*.json")):
            errors.extend(validate_prefix(path, version))

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print("SourceOS control-plane examples validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
