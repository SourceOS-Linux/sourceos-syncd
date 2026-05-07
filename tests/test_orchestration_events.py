import json

from sourceos_syncd.orchestration_events import (
    enqueue_event_records,
    list_event_queue,
    replay_event_queue,
    summarize_event_queue,
    validate_event_record,
)


def record(record_id, outcome, effect_class="low_risk_actuation", approval_mode="notify"):
    return {
        "record_id": record_id,
        "event": {
            "event_id": "event:" + record_id.split(":", 1)[-1],
            "target_node_id": "node:target",
            "causality": {
                "idempotency_key": "idem:" + record_id,
                "policy_epoch": "policy-epoch-0",
            },
        },
        "capability": {
            "capability_id": "capability:" + record_id.split(":", 1)[-1],
            "effect_class": effect_class,
            "required_policy_outcome": outcome,
            "approval_mode": approval_mode,
        },
        "reaction": {
            "reaction_id": "reaction:" + record_id.split(":", 1)[-1],
            "policy_outcome": outcome,
            "status": "scheduled" if outcome in {"allowed", "redacted"} else "blocked_or_waiting",
            "receipt_refs": ["receipt:" + record_id.split(":", 1)[-1]],
            "dead_letter_on_failure": True,
        },
        "evidence_refs": ["receipt:" + record_id.split(":", 1)[-1]],
    }


def test_validate_event_record_maps_states():
    assert validate_event_record(record("record:fan", "allowed"))["state"] == "pending"
    assert validate_event_record(record("record:camera", "redacted", effect_class="observe"))["state"] == "pending"
    assert validate_event_record(record("record:security", "requires_approval", effect_class="high_risk_actuation", approval_mode="explicit_user_approval"))["state"] == "waiting-approval"
    assert validate_event_record(record("record:blocked", "denied", effect_class="high_risk_actuation", approval_mode="not_overridable_in_first_slice"))["state"] == "blocked"


def test_validate_event_record_rejects_missing_idempotency_key():
    item = record("record:broken", "allowed")
    item["event"]["causality"].pop("idempotency_key")

    decision = validate_event_record(item)

    assert decision["state"] == "dead-letter"
    assert "missing idempotency key" in decision["errors"]


def test_enqueue_dedupes_by_idempotency_key(tmp_path):
    records = [record("record:fan", "allowed")]

    first = enqueue_event_records(tmp_path, records)
    second = enqueue_event_records(tmp_path, records)

    assert first["counts"]["pending"] == 1
    assert second["counts"]["pending"] == 1
    assert first["enqueued"][0]["status"] == "queued"
    assert second["enqueued"][0]["status"] == "deduped"


def test_enqueue_partitions_pending_waiting_blocked_and_replay(tmp_path):
    records = [
        record("record:fan", "allowed"),
        record("record:camera", "redacted", effect_class="observe"),
        record("record:security", "requires_approval", effect_class="high_risk_actuation", approval_mode="explicit_user_approval"),
        record("record:blocked", "denied", effect_class="high_risk_actuation", approval_mode="not_overridable_in_first_slice"),
    ]

    result = enqueue_event_records(tmp_path, records)

    assert result["counts"]["pending"] == 2
    assert result["counts"]["waiting-approval"] == 1
    assert result["counts"]["blocked"] == 1
    assert result["counts"]["dead-letter"] == 0

    pending = list_event_queue(tmp_path, state="pending")
    waiting = list_event_queue(tmp_path, state="waiting-approval")
    blocked = list_event_queue(tmp_path, state="blocked")
    replay = replay_event_queue(tmp_path, state="pending")

    assert pending["count"] == 2
    assert waiting["count"] == 1
    assert blocked["count"] == 1
    assert replay["replay"]["non_mutating"] is True
    assert replay["replay"]["count"] == 2


def test_summary_is_json_serializable(tmp_path):
    enqueue_event_records(tmp_path, [record("record:fan", "allowed")])
    summary = summarize_event_queue(tmp_path)

    assert summary["non_mutating"] is True
    json.dumps(summary, sort_keys=True)
