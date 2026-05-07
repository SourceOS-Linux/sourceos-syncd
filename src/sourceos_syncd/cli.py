"""Command line interface for sourceos-syncd state integrity work."""

from __future__ import annotations

import argparse
import json
import sys

from .evidence import load_json_file, make_evidence, validate_evidence, write_evidence_file
from .orchestration_events import (
    enqueue_event_file,
    init_event_queue,
    list_event_queue,
    replay_event_queue,
    summarize_event_queue,
)
from .reports import load_report, pretty_json, repair_plan, snapshot, validate_report, verify, with_fresh_diagnosis
from .scorecard import evaluate_scorecard, validate_scorecard
from .store_reports import append_store_event, init_store, snapshot_from_store
from .trust import TrustRequest, evaluate_trust, validate_trust_decision


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
        description="SourceOS state integrity snapshot, diagnosis, verification, planning, evidence, trust, orchestration, and scorecard tools.",
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

    evidence = subcommands.add_parser("evidence", help="local Lampstand-compatible evidence tools")
    evidence_sub = evidence.add_subparsers(dest="command", required=True)

    wrap = evidence_sub.add_parser("wrap", help="wrap a JSON artifact in an evidence envelope")
    wrap.add_argument("--file", "-f", required=True, help="artifact JSON file")
    wrap.add_argument("--type", required=True, choices=["state-integrity-report", "repair-plan", "policy-decision", "local-state-summary", "agent-trust-decision", "delivery-scorecard"], help="evidence type")
    wrap.add_argument("--subject", required=True, help="evidence subject")
    add_compact(wrap)

    write = evidence_sub.add_parser("write", help="write a local evidence envelope")
    write.add_argument("--file", "-f", required=True, help="artifact JSON file")
    write.add_argument("--type", required=True, choices=["state-integrity-report", "repair-plan", "policy-decision", "local-state-summary", "agent-trust-decision", "delivery-scorecard"], help="evidence type")
    write.add_argument("--subject", required=True, help="evidence subject")
    write.add_argument("--output-dir", required=True, help="directory for evidence envelopes")
    add_compact(write)

    validate = evidence_sub.add_parser("validate", help="validate an evidence envelope")
    validate.add_argument("--file", "-f", required=True, help="evidence envelope JSON file")
    add_compact(validate)

    trust = subcommands.add_parser("trust", help="AgentPlane-compatible trust checks")
    trust_sub = trust.add_subparsers(dest="command", required=True)

    evaluate = trust_sub.add_parser("evaluate", help="evaluate a State Integrity Report for a subject/action/lane")
    evaluate.add_argument("--file", "-f", required=True, help="State Integrity Report JSON file")
    evaluate.add_argument("--subject", required=True, help="request subject")
    evaluate.add_argument("--action", required=True, help="requested action")
    evaluate.add_argument("--lane", default="normal", help="target lane")
    evaluate.add_argument("--allow-degraded", action="store_true", help="allow explicitly degraded mode")
    evaluate.add_argument("--require-attestation", action="store_true", help="require signed attestation")
    add_compact(evaluate)

    trust_validate = trust_sub.add_parser("validate", help="validate an AgentPlane trust decision")
    trust_validate.add_argument("--file", "-f", required=True, help="trust decision JSON file")
    add_compact(trust_validate)

    orchestration = subcommands.add_parser("orchestration", help="event-capability queue, replay, and admission-support commands")
    orchestration_sub = orchestration.add_subparsers(dest="command", required=True)

    orch_init = orchestration_sub.add_parser("init", help="initialize the local orchestration event queue")
    orch_init.add_argument("--root", required=True, help="local store root")
    add_compact(orch_init)

    orch_enqueue = orchestration_sub.add_parser("enqueue", help="enqueue event-capability records or a full event-capability bundle")
    orch_enqueue.add_argument("--root", required=True, help="local store root")
    orch_enqueue.add_argument("--file", "-f", required=True, help="event-capability records or bundle JSON")
    add_compact(orch_enqueue)

    orch_list = orchestration_sub.add_parser("list", help="list queued orchestration events")
    orch_list.add_argument("--root", required=True, help="local store root")
    orch_list.add_argument("--state", choices=["pending", "waiting-approval", "blocked", "dead-letter"], help="optional queue state")
    add_compact(orch_list)

    orch_replay = orchestration_sub.add_parser("replay", help="emit a non-mutating replay artifact for a queue state")
    orch_replay.add_argument("--root", required=True, help="local store root")
    orch_replay.add_argument("--state", default="pending", choices=["pending", "waiting-approval", "blocked", "dead-letter"], help="queue state to replay")
    add_compact(orch_replay)

    orch_summary = orchestration_sub.add_parser("summary", help="summarize the orchestration event queue")
    orch_summary.add_argument("--root", required=True, help="local store root")
    add_compact(orch_summary)

    scorecard = subcommands.add_parser("scorecard", help="Delivery Excellence scorecards")
    scorecard_sub = scorecard.add_subparsers(dest="command", required=True)
    score_eval = scorecard_sub.add_parser("evaluate", help="evaluate a State Integrity Report as a scorecard")
    score_eval.add_argument("--file", "-f", required=True, help="State Integrity Report JSON file")
    add_compact(score_eval)
    score_validate = scorecard_sub.add_parser("validate", help="validate a Delivery Excellence scorecard")
    score_validate.add_argument("--file", "-f", required=True, help="scorecard JSON file")
    add_compact(score_validate)

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

        if args.area == "evidence" and args.command == "wrap":
            artifact = load_json_file(args.file)
            envelope = make_evidence(artifact, args.type, args.subject)
            sys.stdout.write(pretty_json(envelope, pretty=pretty))
            return 0

        if args.area == "evidence" and args.command == "write":
            artifact = load_json_file(args.file)
            envelope = make_evidence(artifact, args.type, args.subject)
            target = write_evidence_file(envelope, args.output_dir)
            sys.stdout.write(pretty_json({"path": str(target), "evidence": envelope}, pretty=pretty))
            return 0

        if args.area == "evidence" and args.command == "validate":
            envelope = load_json_file(args.file)
            errors = validate_evidence(envelope)
            sys.stdout.write(pretty_json({"valid": not errors, "errors": errors}, pretty=pretty))
            return 0 if not errors else 2

        if args.area == "trust" and args.command == "evaluate":
            report = load_json_file(args.file)
            decision = evaluate_trust(
                report,
                TrustRequest(
                    subject=args.subject,
                    action=args.action,
                    lane=args.lane,
                    allow_degraded=args.allow_degraded,
                    require_attestation=args.require_attestation,
                ),
            )
            sys.stdout.write(pretty_json(decision, pretty=pretty))
            return 0 if decision["status"] in {"allowed", "degraded_allowed"} else 2

        if args.area == "trust" and args.command == "validate":
            decision = load_json_file(args.file)
            errors = validate_trust_decision(decision)
            sys.stdout.write(pretty_json({"valid": not errors, "errors": errors}, pretty=pretty))
            return 0 if not errors else 2

        if args.area == "orchestration" and args.command == "init":
            sys.stdout.write(pretty_json(init_event_queue(args.root), pretty=pretty))
            return 0

        if args.area == "orchestration" and args.command == "enqueue":
            sys.stdout.write(pretty_json(enqueue_event_file(args.root, args.file), pretty=pretty))
            return 0

        if args.area == "orchestration" and args.command == "list":
            sys.stdout.write(pretty_json(list_event_queue(args.root, state=args.state), pretty=pretty))
            return 0

        if args.area == "orchestration" and args.command == "replay":
            sys.stdout.write(pretty_json(replay_event_queue(args.root, state=args.state), pretty=pretty))
            return 0

        if args.area == "orchestration" and args.command == "summary":
            sys.stdout.write(pretty_json(summarize_event_queue(args.root), pretty=pretty))
            return 0

        if args.area == "scorecard" and args.command == "evaluate":
            report = load_json_file(args.file)
            scorecard = evaluate_scorecard(report)
            sys.stdout.write(pretty_json(scorecard, pretty=pretty))
            return 0 if scorecard["status"] in {"ready", "watch"} else 2

        if args.area == "scorecard" and args.command == "validate":
            scorecard = load_json_file(args.file)
            errors = validate_scorecard(scorecard)
            sys.stdout.write(pretty_json({"valid": not errors, "errors": errors}, pretty=pretty))
            return 0 if not errors else 2

    except Exception as exc:  # noqa: BLE001 - CLI boundary should present clean error JSON.
        sys.stderr.write(pretty_json({"error": type(exc).__name__, "message": str(exc)}, pretty=pretty))
        return 1

    parser.error("unsupported command")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
