#!/usr/bin/env python3
"""Validate SourceOS process provenance tuples and emit canonical process events."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any, Iterable

from jsonschema import Draft202012Validator, FormatChecker

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROVENANCE_SCHEMA = ROOT / "schemas" / "sourceos.process-provenance.v0.1.schema.json"
EVENT_SCHEMA = ROOT / "schemas" / "sourceos.event.v0.1.schema.json"


def load_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validator_for(schema_path: pathlib.Path) -> Draft202012Validator:
    schema = load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def format_errors(errors: Iterable[Any]) -> list[str]:
    formatted: list[str] = []
    for error in sorted(errors, key=lambda item: list(item.absolute_path)):
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        formatted.append(f"{location}: {error.message}")
    return formatted


def validate_obj(obj: dict[str, Any], schema_path: pathlib.Path) -> list[str]:
    validator = validator_for(schema_path)
    return format_errors(validator.iter_errors(obj))


def fail(prefix: str, errors: list[str]) -> int:
    for error in errors:
        print(f"{prefix}: {error}", file=sys.stderr)
    return 1


def event_base(prov: dict[str, Any], event_id: str, event_class: str, created_at: str, summary: str, why: str, next_action: str) -> dict[str, Any]:
    proc = prov["process_identity"]
    exe = prov["executable_identity"]
    causality = prov["causality"]
    privacy = prov["privacy"]

    return {
        "schema_version": "sourceos.event.v0.1",
        "event_id": event_id,
        "event_class": event_class,
        "lane": "process_lifecycle",
        "severity": "info",
        "outcome": "allowed",
        "created_at": created_at,
        "observed_at_monotonic_ns": 0,
        "host": {
            "host_id": "host_local_pseudonym",
            "platform": "sourceos",
            "kernel": "unknown",
            "privacy_zone": privacy["tier"],
        },
        "actor": {
            "actor_id": f"actor_process_{proc['pid'] if proc['pid'] is not None else 'unknown'}",
            "actor_type": "process",
            "display_name": exe["display_path"],
            "uid": proc["uid_class"],
            "session_id": None,
            "authority_domain": proc["environment_class"],
        },
        "causality": {
            "parent_event_id": causality.get("parent_event_id"),
            "root_event_id": causality["root_event_id"],
            "span_id": causality["span_id"] if event_class == "process.exec" else f"{causality['span_id']}_exit",
            "trace_id": causality["trace_id"],
        },
        "subject": {
            "type": "process",
            "id": f"proc_{proc['pid'] if proc['pid'] is not None else 'unknown'}",
            "display": exe["display_path"],
        },
        "trust": {
            "mode": exe["trust_mode"],
            "signature_state": exe["signature_state"],
            "package_origin": exe["package_origin"],
            "content_hash": exe.get("content_hash"),
            "attestation_state": "verified" if exe["signature_state"] == "valid" else "missing",
            "network_lookup": exe["network_lookup"],
            "degradation_reason": None,
        },
        "privacy": privacy,
        "evidence": [
            {
                "evidence_id": f"ev_process_provenance_{event_class.replace('.', '_')}",
                "source": "process-monitor",
                "raw_ref": "process-provenance-tuple",
                "summary": "Canonical process event generated from SourceOS process provenance tuple."
            }
        ],
        "operator_narrative": {
            "summary": summary,
            "risk": "low",
            "why": why,
            "next_action": next_action,
            "drilldown_refs": [f"ev_process_provenance_{event_class.replace('.', '_')}"]
        },
        "sync": {
            "replication_policy": "local_only",
            "retention_class": "standard",
            "exportable": False
        }
    }


def emit_events(prov: dict[str, Any], created_at: str) -> list[dict[str, Any]]:
    proc = prov["process_identity"]
    exe = prov["executable_identity"]
    root_event_id = prov["causality"]["root_event_id"]

    exec_event = event_base(
        prov,
        event_id=root_event_id,
        event_class="process.exec",
        created_at=created_at,
        summary=f"{exe['display_path']} launched under {proc['environment_class']} context.",
        why=f"The process was classified as {exe['package_origin']} with {exe['signature_state']} signature state and {exe['network_lookup']} network trust lookup.",
        next_action="No action required unless this launch was unexpected."
    )

    events = [exec_event]
    exit_info = proc.get("exit")
    if isinstance(exit_info, dict) and exit_info.get("observed"):
        exit_event = event_base(
            prov,
            event_id=f"{root_event_id}_exit",
            event_class="process.exit",
            created_at=created_at,
            summary=f"{exe['display_path']} exited with code {exit_info.get('exit_code')}.",
            why=f"The exit record stayed attached to trace {prov['causality']['trace_id']} and termination reason was {exit_info.get('termination_reason')}.",
            next_action="No action required unless runtime, signal, or exit status violates policy."
        )
        exit_event["causality"]["parent_event_id"] = root_event_id
        exit_event["evidence"].append({
            "evidence_id": "ev_process_exit_status",
            "source": "process-monitor",
            "raw_ref": "process-provenance-tuple.exit",
            "summary": f"observed={exit_info.get('observed')} exit_code={exit_info.get('exit_code')} signal={exit_info.get('signal')} runtime_ms={exit_info.get('runtime_ms')} termination_reason={exit_info.get('termination_reason')}"
        })
        exit_event["operator_narrative"]["drilldown_refs"].append("ev_process_exit_status")
        events.append(exit_event)

    return events


def cmd_validate(args: argparse.Namespace) -> int:
    path = pathlib.Path(args.provenance)
    obj = load_json(path)
    if not isinstance(obj, dict):
        return fail(str(path), ["expected top-level JSON object"])
    errors = validate_obj(obj, PROVENANCE_SCHEMA)
    if errors:
        return fail(str(path), errors)
    print(f"{path}: valid SourceOS process provenance tuple")
    return 0


def cmd_emit_events(args: argparse.Namespace) -> int:
    path = pathlib.Path(args.provenance)
    obj = load_json(path)
    if not isinstance(obj, dict):
        return fail(str(path), ["expected top-level JSON object"])

    errors = validate_obj(obj, PROVENANCE_SCHEMA)
    if errors:
        return fail(str(path), errors)

    events = emit_events(obj, args.created_at)
    event_errors: list[str] = []
    for event in events:
        event_errors.extend(f"{event['event_id']}: {error}" for error in validate_obj(event, EVENT_SCHEMA))
    if event_errors:
        return fail("generated event invalid", event_errors)

    if args.out_dir:
        out_dir = pathlib.Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for event in events:
            out_path = out_dir / f"{event['event_id']}.json"
            out_path.write_text(json.dumps(event, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(f"wrote {out_path}")
    else:
        print(json.dumps(events, indent=2, sort_keys=True))
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="SourceOS process provenance helper")
    sub = root.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="validate a process provenance tuple")
    validate.add_argument("provenance")
    validate.set_defaults(func=cmd_validate)

    emit = sub.add_parser("emit-events", help="emit canonical process exec/exit events from a provenance tuple")
    emit.add_argument("provenance")
    emit.add_argument("--created-at", default="2026-05-04T19:21:58.455000-04:00")
    emit.add_argument("--out-dir", default=None)
    emit.set_defaults(func=cmd_emit_events)

    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
