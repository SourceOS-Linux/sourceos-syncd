"""Event-capability queue for SourceOS orchestration.

This is a deterministic, standard-library-only bootstrap for event-native
orchestration. It stores event-capability records by idempotency key, preserves
policy outcomes, routes invalid records to dead-letter state, and emits replay
records without mutating devices or external systems.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

QUEUE_SCHEMA = "sourceos.orchestration.event-queue.v0.1"
RECORD_SCHEMA = "sourceos.orchestration.event-record.v0.1"
REPLAY_SCHEMA = "sourceos.orchestration.replay.v0.1"

EXECUTABLE_OUTCOMES = {"allowed", "redacted"}
WAITING_OUTCOMES = {"requires_approval"}
BLOCKING_OUTCOMES = {"denied", "degraded", "requires_local_only"}
HIGH_RISK_EFFECTS = {"high_risk_actuation", "irreversible_action"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_id(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in value.strip())
    cleaned = cleaned.strip(".")
    if not cleaned:
        raise ValueError("idempotency key cannot be empty")
    return cleaned


def queue_paths(root: str | Path) -> dict[str, Path]:
    base = Path(root).expanduser().resolve() / "orchestration"
    return {
        "root": base,
        "manifest": base / "manifest.json",
        "pending": base / "pending",
        "waiting": base / "waiting-approval",
        "blocked": base / "blocked",
        "dead_letter": base / "dead-letter",
        "replay": base / "replay",
        "audit": base / "audit.jsonl",
    }


def init_event_queue(root: str | Path) -> dict[str, Any]:
    paths = queue_paths(root)
    paths["root"].mkdir(parents=True, exist_ok=True)
    for key in ("pending", "waiting", "blocked", "dead_letter", "replay"):
        paths[key].mkdir(exist_ok=True)
    if not paths["audit"].exists():
        paths["audit"].write_text("", encoding="utf-8")
    if not paths["manifest"].exists():
        manifest = {
            "schema": QUEUE_SCHEMA,
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "delivery_mode": "exactly_once_by_idempotency_key",
            "directories": ["pending", "waiting-approval", "blocked", "dead-letter", "replay"],
            "non_mutating": True,
        }
        paths["manifest"].write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return json.loads(paths["manifest"].read_text(encoding="utf-8"))


def load_payload(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def bundle_to_records(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    capabilities = {item.get("capability_id"): item for item in bundle.get("capabilities", []) if isinstance(item, dict)}
    events = {item.get("event_id"): item for item in bundle.get("events", []) if isinstance(item, dict)}
    records = []
    for reaction in bundle.get("reaction_plans", []):
        if not isinstance(reaction, dict):
            continue
        records.append(
            {
                "record_id": "record:" + str(reaction.get("reaction_id", "unknown")).split(":", 1)[-1],
                "mode": "event-capability-evidence-v0",
                "event": events.get(reaction.get("event_id"), {}),
                "capability": capabilities.get(reaction.get("capability_id"), {}),
                "reaction": reaction,
                "evidence_refs": reaction.get("receipt_refs", []),
            }
        )
    return records


def extract_records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        if {"events", "capabilities", "reaction_plans"}.issubset(value):
            return bundle_to_records(value)
        for key in ("records", "results"):
            items = value.get(key)
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
        data = value.get("data")
        if isinstance(data, dict):
            return extract_records(data)
    raise ValueError("input must be records/results or a full event-capability bundle")


def validate_event_record(record: dict[str, Any]) -> dict[str, Any]:
    event = record.get("event") if isinstance(record.get("event"), dict) else {}
    capability = record.get("capability") if isinstance(record.get("capability"), dict) else {}
    reaction = record.get("reaction") if isinstance(record.get("reaction"), dict) else {}
    causality = event.get("causality") if isinstance(event.get("causality"), dict) else {}

    errors: list[str] = []
    warnings: list[str] = []

    event_id = str(event.get("event_id", ""))
    capability_id = str(capability.get("capability_id", ""))
    effect_class = str(capability.get("effect_class", ""))
    policy_outcome = str(reaction.get("policy_outcome", ""))
    required_policy_outcome = str(capability.get("required_policy_outcome", ""))
    idempotency_key = str(causality.get("idempotency_key", ""))
    receipt_refs = record.get("evidence_refs") or reaction.get("receipt_refs") or []

    if not event_id:
        errors.append("missing event_id")
    if not capability_id:
        errors.append("missing capability_id")
    if not idempotency_key:
        errors.append("missing idempotency key")
    if not receipt_refs:
        errors.append("missing evidence receipt references")
    if reaction.get("dead_letter_on_failure") is not True:
        errors.append("dead_letter_on_failure must be true")
    if policy_outcome != required_policy_outcome:
        errors.append("policy outcome does not match capability required_policy_outcome")

    if effect_class in HIGH_RISK_EFFECTS:
        approval_mode = str(capability.get("approval_mode", ""))
        if policy_outcome == "allowed":
            errors.append("high-risk event capability cannot be directly allowed")
        if policy_outcome == "requires_approval" and approval_mode not in {"explicit_user_approval", "two_party_approval", "admin_approval"}:
            errors.append("high-risk approval outcome lacks strict approval mode")
        if policy_outcome == "denied":
            warnings.append("high-risk event capability denied; preserve denial receipt")

    if policy_outcome in EXECUTABLE_OUTCOMES and not errors:
        state = "pending"
    elif policy_outcome in WAITING_OUTCOMES and not errors:
        state = "waiting-approval"
    elif policy_outcome in BLOCKING_OUTCOMES and not errors:
        state = "blocked"
    else:
        state = "dead-letter"

    return {
        "valid": not errors,
        "state": state,
        "errors": errors,
        "warnings": warnings,
        "event_id": event_id,
        "capability_id": capability_id,
        "effect_class": effect_class,
        "policy_outcome": policy_outcome,
        "idempotency_key": idempotency_key,
        "receipt_refs": receipt_refs,
    }


def _state_dir(paths: dict[str, Path], state: str) -> Path:
    if state == "pending":
        return paths["pending"]
    if state == "waiting-approval":
        return paths["waiting"]
    if state == "blocked":
        return paths["blocked"]
    return paths["dead_letter"]


def _write_json(path: Path, obj: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _append_audit(paths: dict[str, Path], item: dict[str, Any]) -> None:
    with paths["audit"].open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, sort_keys=True) + "\n")


def enqueue_event_records(root: str | Path, records: list[dict[str, Any]]) -> dict[str, Any]:
    init_event_queue(root)
    paths = queue_paths(root)
    results = []
    for record in records:
        decision = validate_event_record(record)
        key = decision.get("idempotency_key") or str(record.get("record_id", "missing-id"))
        target = _state_dir(paths, decision["state"]) / f"{safe_id(key)}.json"
        status = "deduped" if target.exists() else "queued"
        envelope = {
            "schema": RECORD_SCHEMA,
            "queued_at": utc_now(),
            "status": status,
            "queue_state": decision["state"],
            "decision": decision,
            "record": record,
        }
        if status == "queued":
            _write_json(target, envelope)
        _append_audit(paths, {"at": utc_now(), "action": status, "queue_state": decision["state"], "idempotency_key": key, "event_id": decision.get("event_id"), "capability_id": decision.get("capability_id")})
        results.append({"idempotency_key": key, "status": status, "queue_state": decision["state"], "errors": decision["errors"], "warnings": decision["warnings"]})
    return summarize_event_queue(root) | {"enqueued": results}


def enqueue_event_file(root: str | Path, input_path: str | Path) -> dict[str, Any]:
    return enqueue_event_records(root, extract_records(load_payload(input_path)))


def list_event_queue(root: str | Path, state: str | None = None) -> dict[str, Any]:
    init_event_queue(root)
    paths = queue_paths(root)
    states = [state] if state else ["pending", "waiting-approval", "blocked", "dead-letter"]
    records = []
    for item_state in states:
        directory = _state_dir(paths, item_state)
        for path in sorted(directory.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            records.append({"path": str(path), "queue_state": item_state, "status": payload.get("status"), "event_id": payload.get("decision", {}).get("event_id"), "capability_id": payload.get("decision", {}).get("capability_id"), "policy_outcome": payload.get("decision", {}).get("policy_outcome"), "idempotency_key": payload.get("decision", {}).get("idempotency_key")})
    return {"schema": QUEUE_SCHEMA, "root": str(paths["root"]), "records": records, "count": len(records)}


def replay_event_queue(root: str | Path, state: str = "pending") -> dict[str, Any]:
    init_event_queue(root)
    paths = queue_paths(root)
    listed = list_event_queue(root, state=state)["records"]
    replay = {
        "schema": REPLAY_SCHEMA,
        "created_at": utc_now(),
        "source_state": state,
        "count": len(listed),
        "records": listed,
        "non_mutating": True,
    }
    target = paths["replay"] / f"replay-{safe_id(state)}-{utc_now().replace(':', '')}.json"
    _write_json(target, replay)
    return {"path": str(target), "replay": replay}


def summarize_event_queue(root: str | Path) -> dict[str, Any]:
    init_event_queue(root)
    paths = queue_paths(root)
    counts = {
        "pending": len(list(paths["pending"].glob("*.json"))),
        "waiting-approval": len(list(paths["waiting"].glob("*.json"))),
        "blocked": len(list(paths["blocked"].glob("*.json"))),
        "dead-letter": len(list(paths["dead_letter"].glob("*.json"))),
        "replay": len(list(paths["replay"].glob("*.json"))),
    }
    return {"schema": QUEUE_SCHEMA, "root": str(paths["root"]), "counts": counts, "non_mutating": True}
