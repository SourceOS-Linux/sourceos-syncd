"""Command line interface for sourceos-syncd state integrity work."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

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
from .content_sync import ContentViewSyncer
from .daemon import SyncDaemon, daemon_from_env
from .katello_client import KatelloContentClient
from .receipt_store import ReceiptStore
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

    sync = subcommands.add_parser("sync", help="Katello content view sync planning and apply")
    sync_sub = sync.add_subparsers(dest="command", required=True)

    def add_katello_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--katello-url", default="https://127.0.0.1:8443", help="Foreman+Katello base URL")
        p.add_argument("--katello-user", default="admin", help="Katello admin username")
        p.add_argument("--katello-password", default=None, help="Katello admin password (or set KATELLO_PASSWORD / KATELLO_PASSWORD_FILE env)")
        p.add_argument("--org", default="SocioProphet", help="Katello organization name")
        p.add_argument("--content-view", default="sourceos-builder-aarch64", help="content view name")
        p.add_argument("--lifecycle-env", default="dev", help="lifecycle environment (dev/candidate/stable)")
        p.add_argument("--locus", default="local", help="execution locus (local/trusted_private)")
        p.add_argument("--flake-ref", default="github:SociOS-Linux/source-os#builder-aarch64", help="NixOS flake ref")
        p.add_argument("--current-version", default=None, help="current content view version (skip if up to date)")
        p.add_argument("--no-verify-ssl", action="store_true", help="skip TLS verification (local dev only)")
        p.add_argument("--signing-public-key", default=None, help="minisign public key (RWS...) to verify nix-cache-info before applying")

    sync_plan = sync_sub.add_parser("plan", help="query Katello and emit a ContentSyncPlan (no changes)")
    add_katello_args(sync_plan)
    add_compact(sync_plan)

    sync_apply = sync_sub.add_parser("apply", help="apply a ContentSyncPlan (dry-run unless --execute)")
    add_katello_args(sync_apply)
    sync_apply.add_argument("--execute", action="store_true", help="actually run nix copy + nixos-rebuild (default: dry-run)")
    sync_apply.add_argument("--store-root", default=None, help="persist receipt to this store root")
    add_compact(sync_apply)

    sync_daemon = sync_sub.add_parser("daemon", help="run the sync daemon (polls Katello; applies on new version)")
    add_katello_args(sync_daemon)
    sync_daemon.add_argument("--poll-interval", type=int, default=300, help="Katello poll interval in seconds (default: 300)")
    sync_daemon.add_argument("--store-root", default=None, help="state + receipt store root (default: /var/lib/sourceos-syncd)")
    sync_daemon.add_argument("--from-env", action="store_true", help="read all config from environment variables (ignores CLI flags)")
    add_compact(sync_daemon)

    sync_check_health = sync_sub.add_parser("check-health", help="run health checks and exit 0 if healthy, 2 if not")
    sync_check_health.add_argument("--store-root", default=None, help="store root to inspect")
    sync_check_health.add_argument("--katello-url", default="https://127.0.0.1:8443", help="Foreman+Katello base URL to probe")
    sync_check_health.add_argument("--no-verify-ssl", action="store_true", help="skip TLS verification")
    add_compact(sync_check_health)

    receipts = subcommands.add_parser("receipts", help="inspect persisted SyncCycleReceipts")
    receipts_sub = receipts.add_subparsers(dest="command", required=True)
    receipts_list = receipts_sub.add_parser("list", help="list recent receipts")
    receipts_list.add_argument("--store-root", default=None, help="store root")
    receipts_list.add_argument("--limit", type=int, default=10, help="number of receipts to show")
    add_compact(receipts_list)
    receipts_last = receipts_sub.add_parser("last", help="show the most recent receipt")
    receipts_last.add_argument("--store-root", default=None, help="store root")
    add_compact(receipts_last)

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

        if args.area == "sync" and args.command in ("plan", "apply"):
            import os
            from .daemon import _resolve_password
            try:
                password = args.katello_password or _resolve_password()
            except RuntimeError as exc:
                sys.stderr.write(pretty_json({"error": "missing password", "message": str(exc)}, pretty=pretty))
                return 1
            client = KatelloContentClient(
                base_url=args.katello_url,
                username=args.katello_user,
                password=password,
                org=args.org,
                verify_ssl=not args.no_verify_ssl,
            )
            manifest = client.get_latest_version(args.content_view, args.lifecycle_env)
            syncer = ContentViewSyncer(
                flake_ref=args.flake_ref,
                locus=args.locus,
                current_version=args.current_version,
                signing_public_key=getattr(args, "signing_public_key", None),
            )
            plan = syncer.plan(manifest)
            if args.command == "plan":
                sys.stdout.write(pretty_json(plan.to_dict(), pretty=pretty))
                return 0 if plan.policy_gate in ("allowed", "no-op") else 2
            result = syncer.execute(plan, dry_run=not args.execute)
            store_root = getattr(args, "store_root", None)
            if store_root and "receipt" in result:
                store = ReceiptStore(root=store_root)
                store.write_receipt(result["receipt"])
                if result.get("status") == "applied":
                    store.write_current_version(manifest.version)
            sys.stdout.write(pretty_json(result, pretty=pretty))
            return 0 if result["status"] in ("dry_run", "applied") else 2

        if args.area == "sync" and args.command == "daemon":
            import logging as _logging
            import os
            _logging.basicConfig(
                level=_logging.INFO,
                format="%(asctime)s %(levelname)s %(name)s %(message)s",
                stream=sys.stderr,
            )
            if getattr(args, "from_env", False):
                daemon = daemon_from_env()
            else:
                from .daemon import _resolve_password
                try:
                    password = args.katello_password or _resolve_password()
                except RuntimeError as exc:
                    sys.stderr.write(pretty_json({"error": "missing password", "message": str(exc)}, pretty=pretty))
                    return 1
                daemon = SyncDaemon(
                    katello_url=args.katello_url,
                    katello_user=args.katello_user,
                    katello_password=password,
                    org=args.org,
                    content_view=args.content_view,
                    lifecycle_env=args.lifecycle_env,
                    locus=args.locus,
                    flake_ref=args.flake_ref,
                    poll_interval_s=args.poll_interval,
                    store_root=getattr(args, "store_root", None),
                    verify_ssl=not args.no_verify_ssl,
                    signing_public_key=getattr(args, "signing_public_key", None),
                )
            return daemon.run()

        if args.area == "sync" and args.command == "check-health":
            import os
            import shutil
            import urllib.request
            store_root = getattr(args, "store_root", None) or "/var/lib/sourceos-syncd"
            store = ReceiptStore(root=store_root)
            checks: dict[str, Any] = {}

            # last receipt outcome
            last = store.last_receipt()
            if last:
                checks["last_receipt_outcome"] = last.get("outcome", "unknown")
                checks["last_receipt_ok"] = last.get("outcome") in ("applied", "dry_run", "planned")
            else:
                checks["last_receipt_outcome"] = "none"
                checks["last_receipt_ok"] = True  # no sync yet is not a failure

            # nix + nixos-rebuild available
            checks["nix_available"] = shutil.which("nix") is not None
            checks["nixos_rebuild_available"] = shutil.which("nixos-rebuild") is not None

            # Katello reachable (non-fatal: daemon tolerates network blips)
            katello_url = getattr(args, "katello_url", "https://127.0.0.1:8443")
            no_verify = getattr(args, "no_verify_ssl", False)
            try:
                import ssl
                ctx = ssl.create_default_context()
                if no_verify:
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                req = urllib.request.urlopen(
                    f"{katello_url}/api/v2/status", context=ctx, timeout=5
                )
                checks["katello_reachable"] = req.status < 500
            except Exception as exc:
                checks["katello_reachable"] = False
                checks["katello_error"] = str(exc)

            healthy = (
                checks.get("last_receipt_ok", True)
                and checks.get("katello_reachable", False)
            )
            output = {"healthy": healthy, "checks": checks}
            sys.stdout.write(pretty_json(output, pretty=pretty))
            return 0 if healthy else 2

        if args.area == "receipts" and args.command == "list":
            store = ReceiptStore(root=getattr(args, "store_root", None) or "/var/lib/sourceos-syncd")
            receipts = store.list_receipts(limit=args.limit)
            sys.stdout.write(pretty_json(receipts, pretty=pretty))
            return 0

        if args.area == "receipts" and args.command == "last":
            store = ReceiptStore(root=getattr(args, "store_root", None) or "/var/lib/sourceos-syncd")
            receipt = store.last_receipt()
            if receipt is None:
                sys.stderr.write(pretty_json({"error": "no receipts found"}, pretty=pretty))
                return 1
            sys.stdout.write(pretty_json(receipt, pretty=pretty))
            return 0

    except Exception as exc:  # noqa: BLE001 - CLI boundary should present clean error JSON.
        sys.stderr.write(pretty_json({"error": type(exc).__name__, "message": str(exc)}, pretty=pretty))
        return 1

    parser.error("unsupported command")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
