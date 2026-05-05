"""State Integrity Report generation, diagnosis, verification, and repair planning."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import platform
import re
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

REQUIRED_IDENTITY_KEYS = {"component", "repo", "pid", "process_name", "node_id_hash", "version", "platform", "service_manager"}
REQUIRED_COLLECTION_KEYS = {"status", "errors", "redacted_fields", "permission_denied_fields", "timed_out_fields", "unavailable_fields"}
REQUIRED_STORE_KEYS = {"name", "role", "backend", "schema_version", "runtime_version", "migration_state", "checksum_state"}
REQUIRED_LANE_KEYS = {"name", "status", "sla", "objects", "journal", "maintenance"}
REQUIRED_INVARIANT_KEYS = {"id", "status", "severity", "evidence", "remediation"}
REQUIRED_REPAIR_KEYS = {"schema", "generated_at", "source_report", "plan_id", "status", "severity", "summary", "policy", "preconditions", "checkpoint", "steps", "blocked_steps", "rollback", "postconditions"}

COLLECTION_STATUSES = {"complete", "partial", "failed"}
STORE_ROLES = {"active", "shadow", "migration", "archive", "repair", "retired", "quarantined", "rebuilding"}
MIGRATION_STATES = {"none", "pending", "lazy", "running", "complete", "failed", "rollback_available"}
CHECKSUM_STATES = {"verified", "unverified", "mismatch", "unsupported"}
LANE_STATUSES = {"active", "dormant", "degraded", "repairing", "retired", "unsafe"}
PRESSURE_STATES = {"none", "watch", "warning", "critical", "unknown"}
INVARIANT_STATUSES = {"pass", "warn", "fail"}
SEVERITIES = {"info", "warning", "error", "critical"}
REPAIR_STATUSES = {"preview", "approved", "running", "complete", "failed", "rolled_back"}

HEX_RE = re.compile(r"^0x[0-9a-fA-F]+$")


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


def is_nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and value >= 0


def path_missing_errors(prefix: str, value: dict[str, Any], required: set[str]) -> list[str]:
    return [f"{prefix}.{key} is required" for key in sorted(required - set(value))]


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


def validate_report(report: dict[str, Any]) -> list[str]:
    """Validate the State Integrity Report contract without external dependencies."""
    errors = validate_shape(report)
    if errors:
        return errors

    if parse_instant(report.get("generated_at")) is None:
        errors.append("generated_at must be an ISO-8601 timestamp")

    identity = report.get("identity")
    if not isinstance(identity, dict):
        errors.append("identity must be an object")
    else:
        errors.extend(path_missing_errors("identity", identity, REQUIRED_IDENTITY_KEYS))
        if not isinstance(identity.get("pid"), int) or identity.get("pid", -1) < 0:
            errors.append("identity.pid must be a non-negative integer")
        if not str(identity.get("node_id_hash", "")).startswith("sha256:"):
            errors.append("identity.node_id_hash must start with sha256:")

    collection = report.get("collection")
    if not isinstance(collection, dict):
        errors.append("collection must be an object")
    else:
        errors.extend(path_missing_errors("collection", collection, REQUIRED_COLLECTION_KEYS))
        if collection.get("status") not in COLLECTION_STATUSES:
            errors.append("collection.status is invalid")
        for key in ["errors", "redacted_fields", "permission_denied_fields", "timed_out_fields", "unavailable_fields"]:
            if not isinstance(collection.get(key), list):
                errors.append(f"collection.{key} must be a list")

    runtime = report.get("runtime")
    if not isinstance(runtime, dict):
        errors.append("runtime must be an object")
    else:
        for key, value in runtime.items():
            if key.endswith("_at") and value is not None and parse_instant(value) is None:
                errors.append(f"runtime.{key} must be null or an ISO-8601 timestamp")

    stores = report.get("stores")
    if not isinstance(stores, list):
        errors.append("stores must be a list")
    else:
        seen_stores: set[str] = set()
        for index, store in enumerate(stores):
            prefix = f"stores[{index}]"
            if not isinstance(store, dict):
                errors.append(f"{prefix} must be an object")
                continue
            errors.extend(path_missing_errors(prefix, store, REQUIRED_STORE_KEYS))
            name = store.get("name")
            if isinstance(name, str):
                if name in seen_stores:
                    errors.append(f"{prefix}.name duplicates store {name!r}")
                seen_stores.add(name)
            if store.get("role") not in STORE_ROLES:
                errors.append(f"{prefix}.role is invalid")
            if store.get("migration_state") not in MIGRATION_STATES:
                errors.append(f"{prefix}.migration_state is invalid")
            if store.get("checksum_state") not in CHECKSUM_STATES:
                errors.append(f"{prefix}.checksum_state is invalid")
            if "flags_raw" in store and not is_nonnegative_int(store.get("flags_raw")):
                errors.append(f"{prefix}.flags_raw must be a non-negative integer")
            if "flags_hex" in store:
                hex_value = store.get("flags_hex")
                if not isinstance(hex_value, str) or not HEX_RE.match(hex_value):
                    errors.append(f"{prefix}.flags_hex must be a hexadecimal string")
                elif is_nonnegative_int(store.get("flags_raw")) and int(hex_value, 16) != store.get("flags_raw"):
                    errors.append(f"{prefix}.flags_hex does not match flags_raw")

    lanes = report.get("lanes")
    if not isinstance(lanes, list) or not lanes:
        errors.append("lanes must be a non-empty list")
    else:
        seen_lanes: set[str] = set()
        for index, lane in enumerate(lanes):
            prefix = f"lanes[{index}]"
            if not isinstance(lane, dict):
                errors.append(f"{prefix} must be an object")
                continue
            errors.extend(path_missing_errors(prefix, lane, REQUIRED_LANE_KEYS))
            name = lane.get("name")
            if isinstance(name, str):
                if name in seen_lanes:
                    errors.append(f"{prefix}.name duplicates lane {name!r}")
                seen_lanes.add(name)
            if lane.get("status") not in LANE_STATUSES:
                errors.append(f"{prefix}.status is invalid")
            for section in ["sla", "objects"]:
                values = lane.get(section, {})
                if not isinstance(values, dict):
                    errors.append(f"{prefix}.{section} must be an object")
                    continue
                for key, value in values.items():
                    if not is_nonnegative_int(value):
                        errors.append(f"{prefix}.{section}.{key} must be a non-negative integer")
            journal = lane.get("journal", {})
            if isinstance(journal, dict):
                for key in ["segment_count", "total_bytes", "max_segment_bytes", "oldest_unapplied_event_age_ms", "replay_lag_events", "replay_lag_bytes", "replay_eta_ms"]:
                    if key in journal and not is_nonnegative_int(journal.get(key)):
                        errors.append(f"{prefix}.journal.{key} must be a non-negative integer")
            else:
                errors.append(f"{prefix}.journal must be an object")

    resources = report.get("resources", {})
    disk = resources.get("disk", {}) if isinstance(resources, dict) else {}
    if not isinstance(disk, dict):
        errors.append("resources.disk must be an object")
    else:
        total = disk.get("total_bytes")
        free = disk.get("free_bytes")
        ratio = disk.get("free_ratio")
        if not is_nonnegative_int(free):
            errors.append("resources.disk.free_bytes must be a non-negative integer")
        if not isinstance(total, int) or total <= 0:
            errors.append("resources.disk.total_bytes must be a positive integer")
        if isinstance(free, int) and isinstance(total, int) and total > 0 and free > total:
            errors.append("resources.disk.free_bytes cannot exceed total_bytes")
        if not isinstance(ratio, (int, float)) or ratio < 0 or ratio > 1:
            errors.append("resources.disk.free_ratio must be between 0 and 1")
        if disk.get("pressure") not in PRESSURE_STATES:
            errors.append("resources.disk.pressure is invalid")

    policy = report.get("policy")
    if not isinstance(policy, dict):
        errors.append("policy must be an object")
    else:
        decisions = policy.get("policy_decisions")
        if not isinstance(decisions, dict):
            errors.append("policy.policy_decisions must be an object")
        else:
            for key, value in decisions.items():
                if not is_nonnegative_int(value):
                    errors.append(f"policy.policy_decisions.{key} must be a non-negative integer")

    invariants = report.get("invariants")
    if not isinstance(invariants, list):
        errors.append("invariants must be a list")
    else:
        for index, invariant in enumerate(invariants):
            prefix = f"invariants[{index}]"
            if not isinstance(invariant, dict):
                errors.append(f"{prefix} must be an object")
                continue
            errors.extend(path_missing_errors(prefix, invariant, REQUIRED_INVARIANT_KEYS))
            if invariant.get("status") not in INVARIANT_STATUSES:
                errors.append(f"{prefix}.status is invalid")
            if invariant.get("severity") not in SEVERITIES:
                errors.append(f"{prefix}.severity is invalid")
            if not isinstance(invariant.get("evidence"), dict):
                errors.append(f"{prefix}.evidence must be an object")

    return errors


def validate_repair_plan(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = sorted(REQUIRED_REPAIR_KEYS - set(plan))
    if missing:
        errors.append(f"missing repair plan keys: {', '.join(missing)}")
    if plan.get("schema") != REPAIR_SCHEMA:
        errors.append(f"unsupported repair plan schema: {plan.get('schema')!r}")
    if parse_instant(plan.get("generated_at")) is None:
        errors.append("generated_at must be an ISO-8601 timestamp")
    if plan.get("status") not in REPAIR_STATUSES:
        errors.append("status is invalid")
    if plan.get("severity") not in SEVERITIES:
        errors.append("severity is invalid")
    policy = plan.get("policy", {})
    if not isinstance(policy, dict):
        errors.append("policy must be an object")
    elif not isinstance(policy.get("destructive_actions_present"), bool):
        errors.append("policy.destructive_actions_present must be boolean")
    steps = plan.get("steps")
    if not isinstance(steps, list) or not steps:
        errors.append("steps must be a non-empty list")
    else:
        expected_order = 1
        for index, step in enumerate(steps):
            prefix = f"steps[{index}]"
            if not isinstance(step, dict):
                errors.append(f"{prefix} must be an object")
                continue
            for key in ["order", "id", "kind", "destructive", "description", "expected_result"]:
                if key not in step:
                    errors.append(f"{prefix}.{key} is required")
            if step.get("order") != expected_order:
                errors.append(f"{prefix}.order must be {expected_order}")
            expected_order += 1
            if not isinstance(step.get("destructive"), bool):
                errors.append(f"{prefix}.destructive must be boolean")
        if plan.get("status") == "preview" and any(step.get("destructive") for step in steps if isinstance(step, dict)):
            errors.append("preview plans cannot include applying mutation steps")
    return errors


def heartbeat_age_ms(report: dict[str, Any]) -> int | None:
    last = parse_instant(report.get("runtime", {}).get("last_heartbeat_at"))
    generated = parse_instant(report.get("generated_at")) or datetime.now(timezone.utc)
    if not last:
        return None
    return max(0, int((generated - last).total_seconds() * 1000))


def verify(report: dict[str, Any]) -> dict[str, Any]:
    invariants: list[dict[str, Any]] = []
    validation_errors = validate_report(report)
    invariants.append({
        "id": "report.contract_valid",
        "status": "pass" if not validation_errors else "fail",
        "severity": "info" if not validation_errors else "critical",
        "evidence": {"errors": validation_errors},
        "remediation": "fix_report_contract",
    })

    age = heartbeat_age_ms(report)
    lane_slas = [lane.get("sla", {}).get("max_heartbeat_age_ms") for lane in report.get("lanes", []) if isinstance(lane, dict)]
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
        if not isinstance(lane, dict):
            continue
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
        if isinstance(store, dict) and store.get("role") == "active" and store.get("shadow_present") and store.get("checksum_state") not in {"verified", "unsupported"}
    ]
    invariants.append({
        "id": "store.shadow_verified_when_present",
        "status": "pass" if not shadow_failures else "warn",
        "severity": "info" if not shadow_failures else "warning",
        "evidence": {"stores": shadow_failures},
        "remediation": "verify_or_rebuild_shadow",
    })

    disk = report.get("resources", {}).get("disk", {})
    pressure = disk.get("pressure", "unknown") if isinstance(disk, dict) else "unknown"
    invariants.append({
        "id": "resources.disk_pressure_below_critical",
        "status": "pass" if pressure not in {"critical", "unknown"} else "fail",
        "severity": "info" if pressure not in {"critical", "unknown"} else "critical",
        "evidence": {"pressure": pressure, "free_ratio": disk.get("free_ratio") if isinstance(disk, dict) else None},
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
        if not isinstance(lane, dict):
            continue
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

    plan = {
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
    return plan


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
