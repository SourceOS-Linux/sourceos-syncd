"""State Integrity Report generation, diagnosis, verification, and repair planning."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import platform
import shutil
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__

STATE_SCHEMA = "sourceos.state-integrity-report/v1alpha1"
REPAIR_SCHEMA = "sourceos.repair-plan/v1alpha1"

REQUIRED_TOP_LEVEL_KEYS = {
    "schema",
    "generated_at",
    "identity",
    "collection",
    "runtime",
    "stores",
    "lanes",
    "pipeline",
    "resources",
    "policy",
    "invariants",
    "diagnosis",
    "controls",
    "attestation",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_instant(value: str | None) -> datetime | None:
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def stable_node_hash() -> str:
    raw = f"{socket.gethostname()}:{platform.node()}".encode("utf-8", errors="ignore")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def service_manager() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "launchd"
    if system == "windows":
        return "windows-service"
    if Path("/run/systemd/system").exists():
        return "systemd"
    return "manual"


def disk_pressure(free_ratio: float) -> str:
    if free_ratio <= 0.05:
        return "critical"
    if free_ratio <= 0.10:
        return "warning"
    if free_ratio <= 0.20:
        return "watch"
    return "none"


def empty_pipeline_counts() -> dict[str, int]:
    return {
        "external_requested": 0,
        "internal_generated": 0,
        "accepted": 0,
        "journaled": 0,
        "applied": 0,
        "deduped": 0,
        "replayed": 0,
        "skipped": 0,
        "failed": 0,
    }


def collect_resources(path: str | os.PathLike[str] = ".") -> dict[str, Any]:
    usage = shutil.disk_usage(path)
    total = max(usage.total, 1)
    free_ratio = round(usage.free / total, 4)
    return {
        "disk": {
            "filesystem": "unknown",
            "free_bytes": usage.free,
            "total_bytes": usage.total,
            "free_ratio": free_ratio,
            "pressure": disk_pressure(free_ratio),
        },
        "memory": {
            "total_gb": None,
            "budget_mb": 256,
            "pressure": "unknown",
            "unavailable_reason": "standard_library_only_collector",
        },
    }


def base_snapshot() -> dict[str, Any]:
    now = utc_now()
    return {
        "schema": STATE_SCHEMA,
        "generated_at": now,
        "identity": {
            "component": "sourceos-syncd",
            "repo": "SourceOS-Linux/sourceos-syncd",
            "pid": os.getpid(),
            "process_name": "sourceos-syncd",
            "node_id_hash": stable_node_hash(),
            "boot_id": "unknown",
            "version": __version__,
            "commit": os.environ.get("SOURCEOS_COMMIT", "unknown"),
            "build_provenance": os.environ.get("SOURCEOS_BUILD_PROVENANCE", "local-dev"),
            "platform": platform.system().lower() or "unknown",
            "service_manager": service_manager(),
        },
        "collection": {
            "status": "partial",
            "duration_ms": 0,
            "errors": [],
            "redacted_fields": [],
            "permission_denied_fields": [],
            "timed_out_fields": [],
            "unavailable_fields": ["memory.total_gb", "identity.boot_id"],
        },
        "runtime": {
            "process_started_at": now,
            "runtime_ready_at": now,
            "store_opened_at": now,
            "replay_started_at": now,
            "replay_completed_at": now,
            "first_heartbeat_at": now,
            "last_heartbeat_at": now,
            "last_clean_shutdown_at": None,
            "last_dirty_open_at": None,
        },
        "stores": [
            {
                "name": "content-store-a",
                "role": "active",
                "backend": "filesystem",
                "schema_version": "1.0.0",
                "created_by_version": __version__,
                "runtime_version": __version__,
                "previous_runtime_version": None,
                "migration_state": "none",
                "active_generation": 1,
                "last_known_good_generation": 1,
                "shadow_present": False,
                "manifest_present": False,
                "checksum_state": "unverified",
                "flags_raw": 0,
                "flags_hex": "0x0",
                "flags_decoded": [],
                "unknown_flags": [],
            }
        ],
        "lanes": [
            {
                "name": "normal",
                "status": "active",
                "sla": {
                    "max_heartbeat_age_ms": 30000,
                    "max_replay_lag_events": 100,
                    "max_replay_lag_ms": 10000,
                },
                "objects": {
                    "total": 0,
                    "tombstones": 0,
                    "orphans": 0,
                    "corrupted": 0,
                    "encrypted": 0,
                    "redacted": 0,
                },
                "journal": {
                    "segment_count": 0,
                    "total_bytes": 0,
                    "max_segment_bytes": 0,
                    "oldest_unapplied_event_age_ms": 0,
                    "replay_lag_events": 0,
                    "replay_lag_bytes": 0,
                    "replay_throughput_events_per_sec": 0,
                    "replay_eta_ms": 0,
                    "checksum_state": "verified",
                },
                "maintenance": {
                    "last_compact_started_at": None,
                    "last_compact_completed_at": None,
                    "last_compact_duration_ms": None,
                    "compaction_debt": "none",
                    "last_purge_started_at": None,
                    "last_purge_completed_at": None,
                    "purge_debt": "none",
                    "last_repair_at": None,
                    "repair_debt": "none",
                },
            }
        ],
        "pipeline": {
            "add": empty_pipeline_counts(),
            "update": empty_pipeline_counts(),
            "delete": {
                "external_requested": 0,
                "authorized": 0,
                "tombstoned": 0,
                "journaled": 0,
                "propagated": 0,
                "purged": 0,
                "failed": 0,
            },
        },
        "resources": collect_resources(Path.home()),
        "policy": {
            "policy_engine": "policy-fabric",
            "policy_version": "unknown",
            "indexing_policy": "sourceos.index/default",
            "retention_policy": "sourceos.retention/local-first-default",
            "replication_policy": "sourceos.replication/local-only",
            "agent_access_policy": "sourceos.agent/trust-gated",
            "policy_decisions": {"allowed": 0, "denied": 0, "redacted": 0, "deferred": 0},
        },
        "invariants": [],
        "diagnosis": {},
        "controls": [],
        "attestation": {"signed": False, "reason": "unsigned-runtime-snapshot"},
    }


def validate_shape(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = sorted(REQUIRED_TOP_LEVEL_KEYS - set(report))
    if missing:
        errors.append(f"missing top-level keys: {', '.join(missing)}")
    if report.get("schema") != STATE_SCHEMA:
        errors.append(f"unsupported schema: {report.get('schema')!r}")
    if not isinstance(report.get("lanes"), list):
        errors.append("lanes must be a list")
    if not isinstance(report.get("stores"), list):
        errors.append("stores must be a list")
    return errors


def heartbeat_age_ms(report: dict[str, Any]) -> int | None:
    last = parse_instant(report.get("runtime", {}).get("last_heartbeat_at"))
    generated = parse_instant(report.get("generated_at")) or datetime.now(timezone.utc)
    if not last:
        return None
    return max(0, int((generated - last).total_seconds() * 1000))


def verify(report: dict[str, Any]) -> dict[str, Any]:
    invariants: list[dict[str, Any]] = []
    shape_errors = validate_shape(report)
    invariants.append({
        "id": "report.shape_valid",
        "status": "pass" if not shape_errors else "fail",
        "severity": "info" if not shape_errors else "critical",
        "evidence": {"errors": shape_errors},
        "remediation": "fix_report_shape",
    })

    age = heartbeat_age_ms(report)
    lane_slas = [lane.get("sla", {}).get("max_heartbeat_age_ms") for lane in report.get("lanes", [])]
    lane_slas = [int(sla) for sla in lane_slas if isinstance(sla, int)]
    max_age = min(lane_slas) if lane_slas else 30000
    invariants.append({
        "id": "heartbeat.within_sla",
        "status": "pass" if age is not None and age <= max_age else "fail",
        "severity": "info" if age is not None and age <= max_age else "error",
        "evidence": {"age_ms": age, "max_heartbeat_age_ms": max_age},
        "remediation": "restart_or_mark_stale",
    })

    total_lag = 0
    allowed_lag = 0
    for lane in report.get("lanes", []):
        total_lag += int(lane.get("journal", {}).get("replay_lag_events") or 0)
        allowed_lag += int(lane.get("sla", {}).get("max_replay_lag_events") or 0)
    invariants.append({
        "id": "journal.replay_lag_within_sla",
        "status": "pass" if total_lag <= allowed_lag else "fail",
        "severity": "info" if total_lag <= allowed_lag else "error",
        "evidence": {"replay_lag_events": total_lag, "allowed_replay_lag_events": allowed_lag},
        "remediation": "run_replay",
    })

    shadow_failures = [
        store.get("name", "unknown")
        for store in report.get("stores", [])
        if store.get("role") == "active" and store.get("shadow_present") and store.get("checksum_state") not in {"verified", "unsupported"}
    ]
    invariants.append({
        "id": "store.shadow_verified_when_present",
        "status": "pass" if not shadow_failures else "warn",
        "severity": "info" if not shadow_failures else "warning",
        "evidence": {"stores": shadow_failures},
        "remediation": "verify_or_rebuild_shadow",
    })

    disk = report.get("resources", {}).get("disk", {})
    pressure = disk.get("pressure", "unknown")
    invariants.append({
        "id": "resources.disk_pressure_below_critical",
        "status": "pass" if pressure not in {"critical", "unknown"} else "fail",
        "severity": "info" if pressure not in {"critical", "unknown"} else "critical",
        "evidence": {"pressure": pressure, "free_ratio": disk.get("free_ratio")},
        "remediation": "compact_or_purge_preview",
    })

    dirty_open = report.get("runtime", {}).get("last_dirty_open_at")
    invariants.append({
        "id": "runtime.no_unrecovered_dirty_open",
        "status": "pass" if not dirty_open else "warn",
        "severity": "info" if not dirty_open else "warning",
        "evidence": {"last_dirty_open_at": dirty_open},
        "remediation": "verify_before_ready",
    })

    order = {"pass": 0, "warn": 1, "fail": 2}
    overall = max(invariants, key=lambda item: order[item["status"]])["status"]
    return {"status": overall, "invariants": invariants}


def diagnose(report: dict[str, Any]) -> dict[str, Any]:
    verification = verify(report)
    causes: list[str] = []
    safe_actions: list[str] = []
    blocked_actions: list[str] = []
    affected_lanes: set[str] = set()

    for invariant in verification["invariants"]:
        if invariant["status"] in {"warn", "fail"}:
            causes.append(invariant["id"])
            if invariant.get("remediation"):
                safe_actions.append(invariant["remediation"])

    for lane in report.get("lanes", []):
        lag = int(lane.get("journal", {}).get("replay_lag_events") or 0)
        allowed = int(lane.get("sla", {}).get("max_replay_lag_events") or 0)
        if lane.get("status") in {"degraded", "repairing", "unsafe"} or lag > allowed:
            affected_lanes.add(lane.get("name", "unknown"))

    collection_status = report.get("collection", {}).get("status")
    if collection_status == "partial":
        causes.append("collection.partial")
    elif collection_status == "failed":
        causes.append("collection.failed")

    disk = report.get("resources", {}).get("disk", {}).get("pressure")
    if disk in {"warning", "critical"}:
        safe_actions.append("purge_preview")
        blocked_actions.append("destructive_purge_without_policy_grant")

    if any("replay_lag" in cause or "heartbeat" in cause for cause in causes):
        blocked_actions.append("agent_action_requiring_fresh_state")

    if any(inv["severity"] == "critical" and inv["status"] == "fail" for inv in verification["invariants"]):
        status, severity = "unsafe", "critical"
    elif any(inv["status"] == "fail" for inv in verification["invariants"]):
        status, severity = "degraded", "error"
    elif any(inv["status"] == "warn" for inv in verification["invariants"]):
        status, severity = "degraded", "warning"
    else:
        status, severity = "healthy", "info"

    summary = {
        "healthy": "All required state integrity invariants pass.",
        "degraded": "One or more state integrity invariants need attention before full trust.",
        "unsafe": "Critical state integrity invariant failed; restrict mutation and require repair planning.",
    }[status]

    return {
        "status": status,
        "severity": severity,
        "summary": summary,
        "causes": sorted(set(causes)),
        "affected_lanes": sorted(affected_lanes),
        "affected_domains": [],
        "safe_actions": sorted(set(safe_actions)) or ["continue_normal_operation"],
        "blocked_actions": sorted(set(blocked_actions)),
    }


def controls_for(report: dict[str, Any]) -> list[dict[str, Any]]:
    diagnosis = diagnose(report)
    controls: list[dict[str, Any]] = []
    if "journal.replay_lag_within_sla" in diagnosis["causes"]:
        controls.append({"id": "run_replay", "trigger": "journal.replay_lag_above_sla", "action": "run_replay", "mode": "automatic_allowed"})
    if report.get("resources", {}).get("disk", {}).get("pressure") in {"warning", "critical"}:
        controls.append({"id": "disk_pressure_purge_preview", "trigger": "disk.pressure_warning_or_critical", "action": "purge_preview", "mode": "manual_approval_required"})
    if "runtime.no_unrecovered_dirty_open" in diagnosis["causes"]:
        controls.append({"id": "verify_dirty_open", "trigger": "runtime.last_dirty_open_present", "action": "verify_before_ready", "mode": "automatic_allowed"})
    return controls


def snapshot() -> dict[str, Any]:
    report = base_snapshot()
    report["invariants"] = verify(report)["invariants"]
    report["diagnosis"] = diagnose(report)
    report["controls"] = controls_for(report)
    return report


def repair_plan(report: dict[str, Any]) -> dict[str, Any]:
    diagnosis = diagnose(report)
    steps: list[dict[str, Any]] = []

    def add_step(step_id: str, kind: str, description: str, expected: str) -> None:
        steps.append({"order": len(steps) + 1, "id": step_id, "kind": kind, "destructive": False, "description": description, "expected_result": expected})

    if "heartbeat.within_sla" in diagnosis["causes"]:
        add_step("mark_stale_and_restart_if_managed", "control", "Mark stale state as degraded and restart only if service management owns the process.", "Freshness is not advertised until a valid heartbeat returns.")
    if "journal.replay_lag_within_sla" in diagnosis["causes"]:
        add_step("run_replay", "replay", "Apply verified journal events until replay lag reaches lane SLA.", "Replay lag falls within the configured lane threshold.")
    if "store.shadow_verified_when_present" in diagnosis["causes"]:
        add_step("verify_or_rebuild_shadow", "verification", "Verify active and shadow generation checksums before any rebuild.", "Shadow state is verified or a follow-up rebuild plan is produced.")
    if "runtime.no_unrecovered_dirty_open" in diagnosis["causes"]:
        add_step("verify_dirty_open_recovery", "verification", "Verify manifest, journal continuity, and last-known-good generation before ready state.", "Dirty-open recovery evidence is recorded and readiness can be reassessed.")
    if report.get("resources", {}).get("disk", {}).get("pressure") in {"watch", "warning", "critical"}:
        add_step("generate_purge_preview", "purge-preview", "List purge-eligible ephemeral and archive objects without deleting them.", "Operator receives policy basis, recoverable bytes, object counts, and audit impact.")
    if not steps:
        add_step("no_op", "control", "No repair action is required because state integrity invariants pass.", "System continues normal operation.")

    return {
        "schema": REPAIR_SCHEMA,
        "generated_at": utc_now(),
        "source_report": {
            "schema": report.get("schema"),
            "component": report.get("identity", {}).get("component"),
            "generated_at": report.get("generated_at"),
        },
        "plan_id": "repair-plan-" + hashlib.sha256(json.dumps(diagnosis, sort_keys=True).encode()).hexdigest()[:16],
        "status": "preview",
        "severity": diagnosis["severity"],
        "summary": diagnosis["summary"],
        "policy": {
            "engine": report.get("policy", {}).get("policy_engine", "policy-fabric"),
            "required_grants": ["sourceos.repair/preview"],
            "destructive_grants_required": ["sourceos.repair/apply", "sourceos.purge/apply"],
            "destructive_actions_present": False,
        },
        "preconditions": [
            {"id": "report.shape_valid", "status": "required", "check": "report schema is supported"},
            {"id": "no_destructive_apply", "status": "required", "check": "this plan is preview-only"},
        ],
        "checkpoint": {"required": True, "type": "last-known-good-generation", "write_audit_record": True},
        "steps": steps,
        "blocked_steps": [{"id": "apply_destructive_changes", "reason": "Requires explicit policy grant, checkpoint, rollback path, and evidence write."}],
        "rollback": {"available": True, "strategy": "restore last-known-good generation and replay only verified journal events", "requires_operator_approval": True},
        "postconditions": [
            "diagnosis.status != unsafe",
            "heartbeat.within_sla in [pass, warn]",
            "journal.replay_lag_within_sla == pass",
            "repair evidence is written when Lampstand is available",
        ],
    }


def load_report(path: str | None) -> dict[str, Any]:
    if not path or path == "-":
        return json.loads(os.sys.stdin.read())
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def pretty_json(data: dict[str, Any], pretty: bool = True) -> str:
    if pretty:
        return json.dumps(data, indent=2, sort_keys=False) + "\n"
    return json.dumps(data, separators=(",", ":"), sort_keys=False) + "\n"


def with_fresh_diagnosis(report: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(report)
    result["invariants"] = verify(result)["invariants"]
    result["diagnosis"] = diagnose(result)
    result["controls"] = controls_for(result)
    return result
