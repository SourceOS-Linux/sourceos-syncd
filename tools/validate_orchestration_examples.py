#!/usr/bin/env python3
"""Validate SourceOS orchestration fixture bundles with stdlib checks."""

from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUNDLE_DIR = ROOT / "examples" / "orchestration"

REQUIRED_TOP_LEVEL = {
    "schema_version",
    "contract_version",
    "bundle_id",
    "data_mode",
    "adapters",
    "device_nodes",
    "events",
    "receipts",
}

OUTCOMES = {"allowed", "denied", "requires_approval", "requires_local_only", "redacted", "degraded"}


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        raise SystemExit(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"{path}: expected top-level JSON object")
    return data


def collect_ids(items: list[dict[str, Any]], field: str, path: pathlib.Path, errors: list[str]) -> set[str]:
    ids: set[str] = set()
    for item in items:
        value = item.get(field)
        if not isinstance(value, str) or not value:
            errors.append(f"{path}: item missing {field}")
            continue
        if value in ids:
            errors.append(f"{path}: duplicate {field} {value}")
        ids.add(value)
    return ids


def validate_bundle(path: pathlib.Path) -> list[str]:
    obj = load_json(path)
    errors: list[str] = []

    missing = REQUIRED_TOP_LEVEL - set(obj)
    for key in sorted(missing):
        errors.append(f"{path}: missing required key {key!r}")

    if obj.get("schema_version") != "sourceos.orchestration.bundle.v0.1":
        errors.append(f"{path}: schema_version must be sourceos.orchestration.bundle.v0.1")
    if obj.get("contract_version") != "sdo.v0.1":
        errors.append(f"{path}: contract_version must be sdo.v0.1")
    if obj.get("data_mode") != "fixture":
        errors.append(f"{path}: bootstrap examples must use data_mode=fixture")

    adapters = obj.get("adapters") or []
    nodes = obj.get("device_nodes") or []
    events = obj.get("events") or []
    receipts = obj.get("receipts") or []

    if not all(isinstance(group, list) for group in (adapters, nodes, events, receipts)):
        errors.append(f"{path}: adapters, device_nodes, events, and receipts must be lists")
        return errors

    adapter_ids = collect_ids(adapters, "adapter_id", path, errors)
    node_ids = collect_ids(nodes, "node_id", path, errors)
    event_ids = collect_ids(events, "event_id", path, errors)
    receipt_ids = collect_ids(receipts, "receipt_id", path, errors)

    for node in nodes:
        adapter = node.get("ecosystem_adapter")
        if adapter not in adapter_ids:
            errors.append(f"{path}: node {node.get('node_id')} references unknown adapter {adapter}")
        if not node.get("trust_state"):
            errors.append(f"{path}: node {node.get('node_id')} missing trust_state")
        if not node.get("revocation_status"):
            errors.append(f"{path}: node {node.get('node_id')} missing revocation_status")

    for event in events:
        event_id = event.get("event_id")
        if event.get("subject_node_id") not in node_ids:
            errors.append(f"{path}: event {event_id} references unknown subject node")
        actor = event.get("actor_id")
        if actor not in node_ids and actor not in adapter_ids:
            errors.append(f"{path}: event {event_id} references unknown actor")
        if event.get("adapter_id") not in adapter_ids:
            errors.append(f"{path}: event {event_id} references unknown adapter")
        privacy = event.get("privacy") or {}
        for key in ("retention_class", "redaction_class", "location_scope"):
            if not privacy.get(key):
                errors.append(f"{path}: event {event_id} missing privacy.{key}")

    for receipt in receipts:
        receipt_id = receipt.get("receipt_id")
        if receipt.get("event_id") not in event_ids:
            errors.append(f"{path}: receipt {receipt_id} references unknown event")
        if receipt.get("subject_node_id") not in node_ids:
            errors.append(f"{path}: receipt {receipt_id} references unknown subject node")
        actor = receipt.get("actor_id")
        if actor not in node_ids and actor not in adapter_ids:
            errors.append(f"{path}: receipt {receipt_id} references unknown actor")
        if receipt.get("source_adapter_id") not in adapter_ids:
            errors.append(f"{path}: receipt {receipt_id} references unknown source adapter")
        if receipt.get("policy_outcome") not in OUTCOMES:
            errors.append(f"{path}: receipt {receipt_id} has invalid policy_outcome")
        for parent in receipt.get("lineage_parent_receipt_ids", []):
            if parent not in receipt_ids:
                errors.append(f"{path}: receipt {receipt_id} references unknown parent {parent}")
        for key in ("retention_class", "redaction_class"):
            if not receipt.get(key):
                errors.append(f"{path}: receipt {receipt_id} missing {key}")

    return errors


def main() -> int:
    errors: list[str] = []
    for path in sorted(BUNDLE_DIR.glob("*.json")):
        errors.extend(validate_bundle(path))

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print("SourceOS orchestration examples validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
