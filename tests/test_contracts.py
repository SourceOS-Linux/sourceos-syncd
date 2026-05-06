from __future__ import annotations

import json
from pathlib import Path

import pytest

from sourceos_syncd.contracts import (
    ActorRecord,
    AgentObjectTransactionRecord,
    ConflictRecord,
    ContractError,
    DeviceTrustRecord,
    IntegrityEventRecord,
    PolicyDecisionRecord,
    ProfileRecord,
    SchemaContractRecord,
    SourceObjectRecord,
    SyncPlanRecord,
    to_json_dict,
    validate_contract,
)

EXAMPLE_DIR = Path("examples/contracts")

EXPECTED_SCHEMAS = {
    "sourceos.profile-record/v1alpha1",
    "sourceos.device-record/v1alpha1",
    "sourceos.actor-record/v1alpha1",
    "sourceos.schema-record/v1alpha1",
    "sourceos.object-record/v1alpha1",
    "sourceos.sync-plan/v1alpha1",
    "sourceos.conflict-record/v1alpha1",
    "sourceos.policy-decision/v1alpha1",
    "sourceos.integrity-event/v1alpha1",
    "sourceos.agent-object-transaction/v1alpha1",
}


def load_example(name: str) -> dict:
    return json.loads((EXAMPLE_DIR / name).read_text(encoding="utf-8"))


def test_all_contract_fixtures_validate() -> None:
    fixtures = sorted(EXAMPLE_DIR.glob("*.json"))
    assert fixtures, "expected contract fixtures"

    seen_schemas: set[str] = set()
    for path in fixtures:
        record = json.loads(path.read_text(encoding="utf-8"))
        validated = validate_contract(record)
        assert validated == record
        seen_schemas.add(record["schema"])

    assert EXPECTED_SCHEMAS <= seen_schemas


def test_contracts_serialize_cleanly_to_json() -> None:
    actor = ActorRecord.from_dict(load_example("actor.agent-one.json"))
    obj = SourceObjectRecord.from_dict(load_example("object.alpha.json"))
    event = IntegrityEventRecord.from_dict(load_example("event.object-alpha-created.json"))

    actor_json = to_json_dict(actor)
    object_json = to_json_dict(obj)
    event_json = to_json_dict(event)

    assert actor_json["schema"] == "sourceos.actor-record/v1alpha1"
    assert object_json["schema"] == "sourceos.object-record/v1alpha1"
    assert event_json["schema"] == "sourceos.integrity-event/v1alpha1"
    json.dumps(actor_json)
    json.dumps(object_json)
    json.dumps(event_json)


def test_each_contract_type_round_trips_from_fixture() -> None:
    mapping = {
        "profile.local-dev.json": ProfileRecord,
        "device.local.json": DeviceTrustRecord,
        "actor.agent-one.json": ActorRecord,
        "schema.source-object-v1.json": SchemaContractRecord,
        "object.alpha.json": SourceObjectRecord,
        "sync-plan.alpha.json": SyncPlanRecord,
        "conflict.alpha.json": ConflictRecord,
        "policy.decision-review.json": PolicyDecisionRecord,
        "event.object-alpha-created.json": IntegrityEventRecord,
        "agent-transaction.alpha.json": AgentObjectTransactionRecord,
    }

    for fixture, contract_type in mapping.items():
        record = load_example(fixture)
        model = contract_type.from_dict(record)
        assert model.to_dict() == record


def test_required_field_validation_rejects_missing_actor_id() -> None:
    record = load_example("actor.agent-one.json")
    record.pop("actor_id")

    with pytest.raises(ContractError, match="missing required fields"):
        validate_contract(record)


def test_controlled_value_validation_rejects_invalid_actor_type() -> None:
    record = load_example("actor.agent-one.json")
    record["actor_type"] = "anonymous_script"

    with pytest.raises(ContractError, match="actor_type"):
        validate_contract(record)


def test_actor_capability_validation_rejects_unknown_capability() -> None:
    record = load_example("actor.agent-one.json")
    record["capabilities"] = ["read", "root_everything"]

    with pytest.raises(ContractError, match="capabilities"):
        validate_contract(record)


def test_policy_effect_validation_rejects_unknown_effect() -> None:
    record = load_example("policy.decision-review.json")
    record["effect"] = "maybe"

    with pytest.raises(ContractError, match="effect"):
        validate_contract(record)


def test_conflict_severity_validation_rejects_unknown_severity() -> None:
    record = load_example("conflict.alpha.json")
    record["severity"] = "panic"

    with pytest.raises(ContractError, match="severity"):
        validate_contract(record)


def test_unsupported_schema_is_rejected() -> None:
    record = {"schema": "sourceos.unknown/v1alpha1"}

    with pytest.raises(ContractError, match="unsupported contract schema"):
        validate_contract(record)
