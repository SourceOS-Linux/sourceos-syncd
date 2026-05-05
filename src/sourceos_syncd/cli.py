"""Command line interface for sourceos-syncd state integrity work."""

from __future__ import annotations

import argparse
import json
import sys

from .reports import load_report, pretty_json, repair_plan, snapshot, validate_report, verify, with_fresh_diagnosis
from .store_reports import (
    append_store_event,
    get_store_record,
    init_store,
    list_store_records,
    put_store_record,
    snapshot_from_store,
)


def add_compact(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--compact",
        action="store_true",
        default=argparse.SUPPRESS,
        help="emit compact JSON",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sourceos-syncd",
        description="SourceOS state integrity snapshot, diagnosis, verification, and planning.",
    )
    parser.add_argument("--compact", action="store_true", help="emit compact JSON")

    subcommands = parser.add_subparsers(dest="area", required=True)

    health = subcommands.add_parser("health", help="health snapshot, explain, and verify commands")
    health_sub = health.add_subparsers(dest="command", required=True)

    snapshot_cmd = health_sub.add_parser("snapshot", help="emit a runtime State Integrity Report snapshot")
    snapshot_cmd.add_argument("--store-root", help="optional local store root to summarize")
    add_compact(snapshot_cmd)

    explain = health_sub.add_parser("explain", help="explain a State Integrity Report")
    explain.add_argument("--file", "-f", default="-", help="report JSON file, or '-' for stdin")
    add_compact(explain)

    verify_cmd = health_sub.add_parser("verify", help="verify State Integrity Report invariants")
    verify_cmd.add_argument("--file", "-f", default="-", help="report JSON file, or '-' for stdin")
    add_compact(verify_cmd)

    repair = subcommands.add_parser("repair", help="planning commands")
    repair_sub = repair.add_subparsers(dest="command", required=True)
    plan = repair_sub.add_parser("plan", help="emit a preview plan")
    plan.add_argument("--file", "-f", default="-", help="report JSON file, or '-' for stdin")
    add_compact(plan)

    store = subcommands.add_parser("store", help="filesystem local store prototype commands")
    store_sub = store.add_subparsers(dest="command", required=True)

    init = store_sub.add_parser("init", help="initialize a local state store")
    init.add_argument("--root", required=True, help="local store root")
    add_compact(init)

    record = store_sub.add_parser("record", help="record a local journal event")
    record.add_argument("--root", required=True, help="local store root")
    record.add_argument("--event-type", required=True, help="event type")
    record.add_argument("--lane", default="normal", help="index lane")
    record.add_argument("--object-id", help="object identifier")
    record.add_argument("--producer", default="manual", help="event producer")
    record.add_argument("--payload-json", default="{}", help="event payload JSON object")
    add_compact(record)

    put_record = store_sub.add_parser("put-record", help="write an actor/schema/object/profile/device registry record")
    put_record.add_argument("--root", required=True, help="local store root")
    put_record.add_argument("--kind", required=True, help="registry kind: profiles, devices, actors, schemas, objects, indexes, repair-reports")
    put_record.add_argument("--record-id", required=True, help="stable record id")
    put_record.add_argument("--record-json", required=True, help="record payload JSON object")
    add_compact(put_record)

    get_record = store_sub.add_parser("get-record", help="read one registry record")
    get_record.add_argument("--root", required=True, help="local store root")
    get_record.add_argument("--kind", required=True, help="registry kind")
    get_record.add_argument("--record-id", required=True, help="stable record id")
    add_compact(get_record)

    list_records = store_sub.add_parser("list-records", help="list records from one registry kind")
    list_records.add_argument("--root", required=True, help="local store root")
    list_records.add_argument("--kind", required=True, help="registry kind")
    add_compact(list_records)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    pretty = not getattr(args, "compact", False)

    try:
        if args.area == "health" and args.command == "snapshot":
            report = snapshot_from_store(args.store_root) if args.store_root else snapshot()
            sys.stdout.write(pretty_json(report, pretty=pretty))
            return 0

        if args.area == "health" and args.command == "explain":
            report = with_fresh_diagnosis(load_report(args.file))
            sys.stdout.write(pretty_json(report["diagnosis"], pretty=pretty))
            return 0 if report["diagnosis"]["status"] == "healthy" else 2

        if args.area == "health" and args.command == "verify":
            report = load_report(args.file)
            contract_errors = validate_report(report)
            result = verify(report)
            output = {"contract_errors": contract_errors, **result}
            sys.stdout.write(pretty_json(output, pretty=pretty))
            return 0 if result["status"] == "pass" else 2

        if args.area == "repair" and args.command == "plan":
            report = load_report(args.file)
            sys.stdout.write(pretty_json(repair_plan(report), pretty=pretty))
            return 0

        if args.area == "store" and args.command == "init":
            sys.stdout.write(pretty_json(init_store(args.root), pretty=pretty))
            return 0

        if args.area == "store" and args.command == "record":
            payload = json.loads(args.payload_json)
            if not isinstance(payload, dict):
                raise ValueError("--payload-json must decode to a JSON object")
            event = append_store_event(args.root, args.event_type, args.lane, args.object_id, args.producer, payload)
            sys.stdout.write(pretty_json(event, pretty=pretty))
            return 0

        if args.area == "store" and args.command == "put-record":
            record = json.loads(args.record_json)
            if not isinstance(record, dict):
                raise ValueError("--record-json must decode to a JSON object")
            stored = put_store_record(args.root, args.kind, args.record_id, record)
            sys.stdout.write(pretty_json(stored, pretty=pretty))
            return 0

        if args.area == "store" and args.command == "get-record":
            sys.stdout.write(pretty_json(get_store_record(args.root, args.kind, args.record_id), pretty=pretty))
            return 0

        if args.area == "store" and args.command == "list-records":
            sys.stdout.write(pretty_json(list_store_records(args.root, args.kind), pretty=pretty))
            return 0

    except Exception as exc:  # noqa: BLE001 - CLI boundary should present clean error JSON.
        sys.stderr.write(pretty_json({"error": type(exc).__name__, "message": str(exc)}, pretty=pretty))
        return 1

    parser.error("unsupported command")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
