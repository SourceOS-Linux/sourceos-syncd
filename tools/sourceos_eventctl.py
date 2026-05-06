#!/usr/bin/env python3
"""Minimal SourceOS canonical event CLI.

This is a seed runtime surface for the control-plane contract. It validates
canonical event files, prints operator narratives, and emits a small canonical
policy-decision event for local testing.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys
import uuid
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
EVENT_SCHEMA = ROOT / "schemas" / "sourceos-event.schema.json"

try:
    from jsonschema import Draft202012Validator
except Exception:  # pragma: no cover
    Draft202012Validator = None  # type: ignore[assignment]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text())


def validate_event_obj(event: dict[str, Any]) -> list[str]:
    if Draft202012Validator is None:
        return ["jsonschema is not installed; run `python3 -m pip install -r requirements-dev.txt`"]

    schema = load_json(EVENT_SCHEMA)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(event), key=lambda item: list(item.absolute_path))
    formatted: list[str] = []
    for error in errors:
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        formatted.append(f"{location}: {error.message}")
    return formatted


def cmd_validate(args: argparse.Namespace) -> int:
    path = pathlib.Path(args.event)
    event = load_json(path)
    errors = validate_event_obj(event)
    if errors:
        for error in errors:
            print(f"{path}: {error}", file=sys.stderr)
        return 1
    print(f"{path}: valid SourceOS canonical event")
    return 0


def cmd_explain(args: argparse.Namespace) -> int:
    event = load_json(pathlib.Path(args.event))
    narrative = event.get("operator_narrative", {})
    print(narrative.get("summary", "No summary provided."))
    print()
    print(f"Risk: {narrative.get('risk', 'unknown')}")
    print(f"Why: {narrative.get('why', 'No explanation provided.')}")
    print(f"Next action: {narrative.get('next_action', 'No next action provided.')}")
    return 0


def policy_event(args: argparse.Namespace) -> dict[str, Any]:
    event_id = f"evt_{uuid.uuid4().hex}"
    return {
        "schema_version": "sourceos.event.v0.1",
        "event_id": event_id,
        "event_class": "policy.decision",
        "lane": "policy",
        "severity": args.severity,
        "outcome": args.outcome,
        "created_at": utc_now(),
        "observed_at_monotonic_ns": None,
        "host": {
            "host_id": args.host_id,
            "platform": "sourceos",
            "kernel": None,
            "privacy_zone": "user_private",
        },
        "actor": {
            "actor_id": args.actor_id,
            "actor_type": args.actor_type,
            "display_name": args.actor,
            "uid": None,
            "session_id": args.session_id,
            "authority_domain": args.authority_domain,
        },
        "causality": {
            "parent_event_id": args.parent_event_id,
            "root_event_id": event_id if args.root_event_id is None else args.root_event_id,
            "span_id": f"span_{uuid.uuid4().hex[:12]}",
            "trace_id": args.trace_id or f"trace_{uuid.uuid4().hex}",
        },
        "subject": {
            "type": args.subject_type,
            "id": args.subject_id,
            "display": args.subject,
        },
        "decision": {
            "decision_id": f"dec_{uuid.uuid4().hex}",
            "policy_bundle": args.policy_bundle,
            "policy_rule": args.policy_rule,
            "operation": args.operation,
            "target_class": args.target_class,
            "result": args.result,
            "semantic_outcome": args.outcome,
            "explanation_code": args.explanation_code,
        },
        "trust": {
            "mode": "local_first",
            "signature_state": "not_applicable",
            "package_origin": "unknown",
            "content_hash": None,
            "attestation_state": "not_applicable",
            "network_lookup": "not_attempted",
        },
        "noise_control": {
            "event_fingerprint": args.fingerprint,
            "first_seen": utc_now(),
            "last_seen": utc_now(),
            "count": 1,
            "suppressed_count": 0,
            "coalesce_window_ms": 0,
        },
        "privacy": {
            "tier": "user_private",
            "redaction_policy": "preserve_causality",
            "secret_fields": [],
        },
        "evidence": [],
        "operator_narrative": {
            "summary": args.summary,
            "risk": args.risk,
            "why": args.why,
            "next_action": args.next_action,
        },
        "sync": {
            "replication_policy": "local_only",
            "retention_class": "standard",
            "exportable": False,
        },
    }


def cmd_emit_policy_decision(args: argparse.Namespace) -> int:
    event = policy_event(args)
    errors = validate_event_obj(event)
    if errors:
        for error in errors:
            print(f"generated event invalid: {error}", file=sys.stderr)
        return 1
    print(json.dumps(event, indent=2, sort_keys=True))
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="SourceOS canonical event control CLI")
    sub = root.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="validate a canonical event JSON file")
    validate.add_argument("event")
    validate.set_defaults(func=cmd_validate)

    explain = sub.add_parser("explain", help="print an event operator narrative")
    explain.add_argument("event")
    explain.set_defaults(func=cmd_explain)

    emit = sub.add_parser("emit-policy-decision", help="emit a minimal canonical policy decision event")
    emit.add_argument("--actor", required=True)
    emit.add_argument("--actor-id", default="actor_local")
    emit.add_argument("--actor-type", default="service", choices=["process", "agent", "user", "service", "kernel", "policy_engine"])
    emit.add_argument("--authority-domain", default="system")
    emit.add_argument("--host-id", default="host_local")
    emit.add_argument("--session-id", default=None)
    emit.add_argument("--subject", required=True)
    emit.add_argument("--subject-id", default="subject_local")
    emit.add_argument("--subject-type", default="ipc_service")
    emit.add_argument("--policy-bundle", default="sourceos.baseline")
    emit.add_argument("--policy-rule", required=True)
    emit.add_argument("--operation", required=True)
    emit.add_argument("--target-class", required=True)
    emit.add_argument("--result", default="deny", choices=["allow", "deny", "defer", "audit"])
    emit.add_argument("--outcome", default="blocked_expected", choices=["allowed", "blocked_expected", "blocked_unexpected", "blocked_attack_like", "degraded", "failed"])
    emit.add_argument("--severity", default="notice", choices=["trace", "debug", "info", "notice", "warning", "error", "critical"])
    emit.add_argument("--explanation-code", required=True)
    emit.add_argument("--fingerprint", default="fp_local_policy_decision")
    emit.add_argument("--summary", required=True)
    emit.add_argument("--risk", default="low", choices=["none", "low", "medium", "high", "critical", "unknown"])
    emit.add_argument("--why", required=True)
    emit.add_argument("--next-action", required=True)
    emit.add_argument("--parent-event-id", default=None)
    emit.add_argument("--root-event-id", default=None)
    emit.add_argument("--trace-id", default=None)
    emit.set_defaults(func=cmd_emit_policy_decision)

    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
