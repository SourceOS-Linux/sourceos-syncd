"""Command line interface for sourceos-syncd state integrity work."""

from __future__ import annotations

import argparse
import sys

from .reports import load_report, pretty_json, repair_plan, snapshot, validate_shape, verify, with_fresh_diagnosis


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sourceos-syncd",
        description="SourceOS state integrity snapshot, diagnosis, verification, and repair planning.",
    )
    parser.add_argument("--compact", action="store_true", help="emit compact JSON")

    subcommands = parser.add_subparsers(dest="area", required=True)

    health = subcommands.add_parser("health", help="health snapshot, explain, and verify commands")
    health_sub = health.add_subparsers(dest="command", required=True)

    health_sub.add_parser("snapshot", help="emit a runtime State Integrity Report snapshot")

    explain = health_sub.add_parser("explain", help="explain a State Integrity Report")
    explain.add_argument("--file", "-f", default="-", help="report JSON file, or '-' for stdin")

    verify_cmd = health_sub.add_parser("verify", help="verify State Integrity Report invariants")
    verify_cmd.add_argument("--file", "-f", default="-", help="report JSON file, or '-' for stdin")

    repair = subcommands.add_parser("repair", help="non-destructive repair planning")
    repair_sub = repair.add_subparsers(dest="command", required=True)
    plan = repair_sub.add_parser("plan", help="emit a non-destructive repair plan")
    plan.add_argument("--file", "-f", default="-", help="report JSON file, or '-' for stdin")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    pretty = not args.compact

    try:
        if args.area == "health" and args.command == "snapshot":
            sys.stdout.write(pretty_json(snapshot(), pretty=pretty))
            return 0

        if args.area == "health" and args.command == "explain":
            report = with_fresh_diagnosis(load_report(args.file))
            sys.stdout.write(pretty_json(report["diagnosis"], pretty=pretty))
            return 0 if report["diagnosis"]["status"] == "healthy" else 2

        if args.area == "health" and args.command == "verify":
            report = load_report(args.file)
            shape_errors = validate_shape(report)
            result = verify(report)
            output = {"shape_errors": shape_errors, **result}
            sys.stdout.write(pretty_json(output, pretty=pretty))
            return 0 if result["status"] == "pass" else 2

        if args.area == "repair" and args.command == "plan":
            report = load_report(args.file)
            sys.stdout.write(pretty_json(repair_plan(report), pretty=pretty))
            return 0

    except Exception as exc:  # noqa: BLE001 - CLI boundary should present clean error JSON.
        sys.stderr.write(pretty_json({"error": type(exc).__name__, "message": str(exc)}, pretty=pretty))
        return 1

    parser.error("unsupported command")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
