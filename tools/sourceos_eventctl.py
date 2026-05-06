#!/usr/bin/env python3
"""Minimal SourceOS canonical event CLI.

This is a seed runtime surface for the control-plane contract. It validates
canonical event files, prints operator narratives, emits small canonical policy
events, and maintains a local append-only JSONL event store.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import sys
import uuid
from typing import Any, Iterable

ROOT = pathlib.Path(__file__).resolve().parents[1]
EVENT_SCHEMA = ROOT / "schemas" / "sourceos.event.v0.1.schema.json"
DEFAULT_STORE = pathlib.Path(".sourceos/events.jsonl")

try:
    from jsonschema import Draft202012Validator, FormatChecker
except Exception:  # pragma: no cover
    Draft202012Validator = None  # type: ignore[assignment]
    FormatChecker = None  # type: ignore[assignment]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text())


def compact_json(obj: dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def event_summary(event: dict[str, Any]) -> str:
    narrative = event.get("operator_narrative", {})
    return str(narrative.get("summary") or "")


def validate_event_obj(event: dict[str, Any]) -> list[str]:
    if Draft202012Validator is None or FormatChecker is None:
        return ["jsonschema is not installed; run `python3 -m pip install -r requirements-dev.txt`"]

    schema = load_json(EVENT_SCHEMA)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(event), key=lambda item: list(item.absolute_path))
    formatted: list[str] = []
    for error in errors:
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        formatted.append(f"{location}: {error.message}")
    return formatted


def fail_validation(prefix: str, errors: Iterable[str]) -> int:
    for error in errors:
        print(f"{prefix}: {error}", file=sys.stderr)
    return 1


def load_valid_event(path: pathlib.Path) -> tuple[dict[str, Any] | None, list[str]]:
    obj = load_json(path)
    if not isinstance(obj, dict):
        return None, ["expected top-level JSON object"]
    errors = validate_event_obj(obj)
    return obj, errors


def iter_store(store: pathlib.Path) -> Iterable[tuple[int, dict[str, Any] | None, str | None]]:
    if not store.exists():
        return
    with store.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            raw = line.strip()
            if not raw:
                continue
            try:
                event = json.loads(raw)
            except Exception as exc:
                yield line_no, None, f"invalid JSONL record: {exc}"
                continue
            if not isinstance(event, dict):
                yield line_no, None, "JSONL record is not an object"
                continue
            yield line_no, event, None


def store_digest(store: pathlib.Path) -> str:
    digest = hashlib.sha256()
    if store.exists():
        with store.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def append_event(store: pathlib.Path, event: dict[str, Any]) -> None:
    store.parent.mkdir(parents=True, exist_ok=True)
    with store.open("a", encoding="utf-8") as handle:
        handle.write(compact_json(event))
        handle.write("\n")


def find_event(store: pathlib.Path, event_id: str) -> dict[str, Any] | None:
    for _, event, error in iter_store(store):
        if error or event is None:
            continue
        if event.get("event_id") == event_id:
            return event
    return None


def cmd_validate(args: argparse.Namespace) -> int:
    path = pathlib.Path(args.event)
    _, errors = load_valid_event(path)
    if errors:
        return fail_validation(str(path), errors)
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


def cmd_write(args: argparse.Namespace) -> int:
    path = pathlib.Path(args.event)
    event, errors = load_valid_event(path)
    if errors or event is None:
        return fail_validation(str(path), errors)

    store = pathlib.Path(args.store)
    if args.reject_duplicate and find_event(store, str(event["event_id"])) is not None:
        print(f"{store}: duplicate event_id {event['event_id']}", file=sys.stderr)
        return 1

    append_event(store, event)
    print(f"wrote {event['event_id']} to {store}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    store = pathlib.Path(args.store)
    count = 0
    for line_no, event, error in iter_store(store):
        if error or event is None:
            print(f"{store}:{line_no}: {error}", file=sys.stderr)
            return 1
        count += 1
        fields = [
            str(event.get("event_id", "<missing>")),
            str(event.get("created_at", "<missing>")),
            str(event.get("event_class", "<missing>")),
            str(event.get("severity", "<missing>")),
            str(event.get("outcome", "<missing>")),
            event_summary(event),
        ]
        print("\t".join(fields))
    if count == 0 and args.fail_empty:
        print(f"{store}: no events", file=sys.stderr)
        return 1
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    store = pathlib.Path(args.store)
    event = find_event(store, args.event_id)
    if event is None:
        print(f"{store}: event not found: {args.event_id}", file=sys.stderr)
        return 1
    print(json.dumps(event, indent=2, sort_keys=True))
    return 0


def cmd_verify_store(args: argparse.Namespace) -> int:
    store = pathlib.Path(args.store)
    seen: set[str] = set()
    errors: list[str] = []
    count = 0

    for line_no, event, parse_error in iter_store(store):
        if parse_error or event is None:
            errors.append(f"{store}:{line_no}: {parse_error}")
            continue
        count += 1
        event_id = str(event.get("event_id", ""))
        if event_id in seen:
            errors.append(f"{store}:{line_no}: duplicate event_id {event_id}")
        else:
            seen.add(event_id)
        for validation_error in validate_event_obj(event):
            errors.append(f"{store}:{line_no}: {validation_error}")

    if count == 0 and args.fail_empty:
        errors.append(f"{store}: no events")

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(f"{store}: verified {count} events ({store_digest(store)})")
    return 0


def policy_event(args: argparse.Namespace) -> dict[str, Any]:
    event_id = f"evt_{uuid.uuid4().hex}"
    now = utc_now()
    return {
        "schema_version": "sourceos.event.v0.1",
        "event_id": event_id,
        "event_class": "policy.decision",
        "lane": "policy",
        "severity": args.severity,
        "outcome": args.outcome,
        "created_at": now,
        "observed_at_monotonic_ns": 0,
        "host": {
            "host_id": args.host_id,
            "platform": "sourceos",
            "kernel": "unknown",
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
            "first_seen": now,
            "last_seen": now,
            "count": 1,
            "suppressed_count": 0,
            "coalesce_window_ms": 1,
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
        return fail_validation("generated event invalid", errors)

    if args.store:
        append_event(pathlib.Path(args.store), event)
        print(f"wrote {event['event_id']} to {args.store}")
    else:
        print(json.dumps(event, indent=2, sort_keys=True))
    return 0


def add_store_arg(command: argparse.ArgumentParser) -> None:
    command.add_argument("--store", default=str(DEFAULT_STORE), help="append-only JSONL event store path")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="SourceOS canonical event control CLI")
    sub = root.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="validate a canonical event JSON file")
    validate.add_argument("event")
    validate.set_defaults(func=cmd_validate)

    explain = sub.add_parser("explain", help="print an event operator narrative")
    explain.add_argument("event")
    explain.set_defaults(func=cmd_explain)

    write = sub.add_parser("write", help="validate and append an event JSON file to a local JSONL store")
    write.add_argument("event")
    add_store_arg(write)
    write.add_argument("--allow-duplicate", dest="reject_duplicate", action="store_false", help="allow duplicate event IDs")
    write.set_defaults(func=cmd_write, reject_duplicate=True)

    list_cmd = sub.add_parser("list", help="list events from a local JSONL store")
    add_store_arg(list_cmd)
    list_cmd.add_argument("--fail-empty", action="store_true")
    list_cmd.set_defaults(func=cmd_list)

    show = sub.add_parser("show", help="show one event from a local JSONL store by event_id")
    show.add_argument("event_id")
    add_store_arg(show)
    show.set_defaults(func=cmd_show)

    verify_store = sub.add_parser("verify-store", help="validate every event in a local JSONL store and print its digest")
    add_store_arg(verify_store)
    verify_store.add_argument("--fail-empty", action="store_true")
    verify_store.set_defaults(func=cmd_verify_store)

    emit = sub.add_parser("emit-policy-decision", help="emit a minimal canonical policy decision event")
    emit.add_argument("--actor", required=True)
    emit.add_argument("--actor-id", default="actor_local")
    emit.add_argument("--actor-type", default="service", choices=["process", "agent", "user", "service", "kernel", "policy_engine"])
    emit.add_argument("--authority-domain", default="system")
    emit.add_argument("--host-id", default="host_local")
    emit.add_argument("--session-id", default=None)
    emit.add_argument("--subject", required=True)
    emit.add_argument("--subject-id", default="subject_local")
    emit.add_argument("--subject-type", default="ipc_service", choices=["process", "file", "socket", "ipc_service", "object", "schema", "replica", "policy", "trust_root", "package", "power_state"])
    emit.add_argument("--policy-bundle", default="sourceos.baseline")
    emit.add_argument("--policy-rule", required=True)
    emit.add_argument("--operation", required=True)
    emit.add_argument("--target-class", required=True)
    emit.add_argument("--result", default="deny", choices=["allow", "deny", "defer", "degrade"])
    emit.add_argument("--outcome", default="blocked_expected", choices=["allowed", "blocked_expected", "blocked_unexpected", "blocked_attack_like", "degraded", "failed", "observed"])
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
    emit.add_argument("--store", default=None, help="when set, append generated event to this JSONL store instead of stdout")
    emit.set_defaults(func=cmd_emit_policy_decision)

    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
