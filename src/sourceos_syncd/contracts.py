"""State Integrity contract models.

These models are intentionally standard-library-only and JSON-first. They are
not a database schema and they do not replace the State Integrity Report. They
provide the next contract layer for actors, objects, schemas, sync plans,
conflicts, policies, events, profiles, devices, and agent transactions.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, ClassVar


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class ContractError(ValueError):
    """Raised when a State Integrity contract record is invalid."""


def require_fields(record: dict[str, Any], required: set[str], contract_name: str) -> None:
    missing = sorted(required - set(record))
    if missing:
        raise ContractError(f"{contract_name} missing required fields: {', '.join(missing)}")


def require_allowed(value: str, allowed: set[str], field_name: str, contract_name: str) -> None:
    if value not in allowed:
        raise ContractError(f"{contract_name}.{field_name} must be one of {sorted(allowed)}, got {value!r}")


def require_list(record: dict[str, Any], field_name: str, contract_name: str) -> None:
    if not isinstance(record.get(field_name), list):
        raise ContractError(f"{contract_name}.{field_name} must be a list")


def require_mapping(record: dict[str, Any], field_name: str, contract_name: str) -> None:
    if not isinstance(record.get(field_name), dict):
        raise ContractError(f"{contract_name}.{field_name} must be an object")


ACTOR_TYPES = {"human", "app", "agent", "device", "service", "import_bridge", "export_bridge", "model_runtime", "remote_relay"}
ACTOR_CAPABILITIES = {"read", "write", "delete", "merge", "repair", "migrate_schema", "export", "replicate"}
TRUST_LEVELS = {"local", "user", "workspace", "org", "external", "quarantined"}
PRIVACY_CLASSES = {"public", "personal", "work", "confidential", "regulated", "secret"}
SYNC_VISIBILITIES = {"local_only", "profile", "workspace", "org", "public"}
RETENTION_CLASSES = {"ephemeral", "normal", "retained", "legal_hold"}
OBJECT_STATES = {"active", "deleted", "tombstoned", "quarantined", "conflicted"}
SYNC_OPERATION_CLASSES = {"replicate", "import", "export", "repair", "migrate", "delete", "restore"}
SYNC_PLAN_STATUSES = {"planned", "blocked", "running", "failed", "completed", "cancelled"}
CONFLICT_SEVERITIES = {"info", "warning", "review_required", "blocking"}
POLICY_EFFECTS = {"allow", "deny", "review_required"}
TRANSACTION_OPERATIONS = {"create", "update", "delete", "merge", "repair", "migrate"}
TRANSACTION_STATUSES = {"draft", "proposed", "approved", "applied", "rejected", "reverted"}
DEVICE_STATES = {"trusted", "untrusted", "revoked", "quarantined"}
PROFILE_CLASSES = {"personal", "work", "client", "air_gapped", "lab", "public_open_source"}


@dataclass(slots=True)
class JsonContract:
    """Base class for JSON-serializable contracts."""

    schema: ClassVar[str]
    required_fields: ClassVar[set[str]] = set()
    controlled_fields: ClassVar[dict[str, set[str]]] = {}
    list_fields: ClassVar[set[str]] = set()
    mapping_fields: ClassVar[set[str]] = set()

    def to_dict(self) -> dict[str, Any]:
        data = dataclasses.asdict(self)
        data.setdefault("schema", self.schema)
        return data

    @classmethod
    def validate_dict(cls, record: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(record, dict):
            raise ContractError(f"{cls.__name__} must be a JSON object")
        require_fields(record, cls.required_fields, cls.__name__)
        for field_name, allowed in cls.controlled_fields.items():
            require_allowed(str(record.get(field_name)), allowed, field_name, cls.__name__)
        for field_name in cls.list_fields:
            require_list(record, field_name, cls.__name__)
        for field_name in cls.mapping_fields:
            require_mapping(record, field_name, cls.__name__)
        return record

    @classmethod
    def from_dict(cls, record: dict[str, Any]) -> JsonContract:
        cls.validate_dict(record)
        allowed = {field.name for field in dataclasses.fields(cls)}
        values = {key: value for key, value in record.items() if key in allowed}
        return cls(**values)  # type: ignore[arg-type]


@dataclass(slots=True)
class ProfileRecord(JsonContract):
    schema: ClassVar[str] = "sourceos.profile-record/v1alpha1"
    required_fields: ClassVar[set[str]] = {"profile_id", "display_name", "profile_class", "created_at", "policy_tags"}
    controlled_fields: ClassVar[dict[str, set[str]]] = {"profile_class": PROFILE_CLASSES}
    list_fields: ClassVar[set[str]] = {"policy_tags"}

    profile_id: str
    display_name: str
    profile_class: str
    created_at: str
    policy_tags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DeviceTrustRecord(JsonContract):
    schema: ClassVar[str] = "sourceos.device-record/v1alpha1"
    required_fields: ClassVar[set[str]] = {"device_id", "display_name", "trust_level", "device_state", "created_at"}
    controlled_fields: ClassVar[dict[str, set[str]]] = {"trust_level": TRUST_LEVELS, "device_state": DEVICE_STATES}

    device_id: str
    display_name: str
    trust_level: str
    device_state: str
    created_at: str
    revoked_at: str | None = None


@dataclass(slots=True)
class ActorRecord(JsonContract):
    schema: ClassVar[str] = "sourceos.actor-record/v1alpha1"
    required_fields: ClassVar[set[str]] = {
        "actor_id",
        "actor_type",
        "display_name",
        "identity_id",
        "workspace_scope",
        "profile_scope",
        "capabilities",
        "trust_level",
        "policy_subject",
        "signing_key_ref",
        "created_at",
    }
    controlled_fields: ClassVar[dict[str, set[str]]] = {"actor_type": ACTOR_TYPES, "trust_level": TRUST_LEVELS}
    list_fields: ClassVar[set[str]] = {"workspace_scope", "profile_scope", "capabilities"}

    actor_id: str
    actor_type: str
    display_name: str
    identity_id: str
    workspace_scope: list[str]
    profile_scope: list[str]
    capabilities: list[str]
    trust_level: str
    policy_subject: str
    signing_key_ref: str
    created_at: str
    revoked_at: str | None = None

    @classmethod
    def validate_dict(cls, record: dict[str, Any]) -> dict[str, Any]:
        JsonContract.validate_dict.__func__(cls, record)
        invalid = sorted(set(record.get("capabilities", [])) - ACTOR_CAPABILITIES)
        if invalid:
            raise ContractError(f"ActorRecord.capabilities contains invalid values: {invalid}")
        return record


@dataclass(slots=True)
class SchemaContractRecord(JsonContract):
    schema: ClassVar[str] = "sourceos.schema-record/v1alpha1"
    required_fields: ClassVar[set[str]] = {
        "schema_id",
        "object_type",
        "schema_version",
        "required_fields",
        "field_owners",
        "migration_policy",
        "conflict_policy",
        "tombstone_policy",
        "sync_visibility",
        "retention_class",
    }
    controlled_fields: ClassVar[dict[str, set[str]]] = {"sync_visibility": SYNC_VISIBILITIES, "retention_class": RETENTION_CLASSES}
    list_fields: ClassVar[set[str]] = {"required_fields"}
    mapping_fields: ClassVar[set[str]] = {"field_owners"}

    schema_id: str
    object_type: str
    schema_version: str
    declared_required_fields: list[str]
    field_owners: dict[str, str]
    migration_policy: str
    conflict_policy: str
    tombstone_policy: str
    sync_visibility: str
    retention_class: str

    def to_dict(self) -> dict[str, Any]:
        data = dataclasses.asdict(self)
        data["required_fields"] = data.pop("declared_required_fields")
        data.setdefault("schema", self.schema)
        return data

    @classmethod
    def from_dict(cls, record: dict[str, Any]) -> SchemaContractRecord:
        cls.validate_dict(record)
        return cls(
            schema_id=record["schema_id"],
            object_type=record["object_type"],
            schema_version=record["schema_version"],
            declared_required_fields=list(record["required_fields"]),
            field_owners=dict(record["field_owners"]),
            migration_policy=record["migration_policy"],
            conflict_policy=record["conflict_policy"],
            tombstone_policy=record["tombstone_policy"],
            sync_visibility=record["sync_visibility"],
            retention_class=record["retention_class"],
        )


@dataclass(slots=True)
class SourceObjectRecord(JsonContract):
    schema: ClassVar[str] = "sourceos.object-record/v1alpha1"
    required_fields: ClassVar[set[str]] = {
        "object_id",
        "object_type",
        "schema_id",
        "schema_version",
        "workspace_id",
        "profile_id",
        "owner_identity",
        "created_by_actor",
        "last_modified_by_actor",
        "created_at",
        "updated_at",
        "privacy_class",
        "sync_visibility",
        "retention_class",
        "policy_tags",
        "provenance",
        "state",
    }
    controlled_fields: ClassVar[dict[str, set[str]]] = {
        "privacy_class": PRIVACY_CLASSES,
        "sync_visibility": SYNC_VISIBILITIES,
        "retention_class": RETENTION_CLASSES,
        "state": OBJECT_STATES,
    }
    list_fields: ClassVar[set[str]] = {"policy_tags", "provenance"}

    object_id: str
    object_type: str
    schema_id: str
    schema_version: str
    workspace_id: str
    profile_id: str
    owner_identity: str
    created_by_actor: str
    last_modified_by_actor: str
    created_at: str
    updated_at: str
    privacy_class: str
    sync_visibility: str
    retention_class: str
    policy_tags: list[str]
    provenance: list[str]
    state: str
    content_hash: str | None = None


@dataclass(slots=True)
class SyncPlanRecord(JsonContract):
    schema: ClassVar[str] = "sourceos.sync-plan/v1alpha1"
    required_fields: ClassVar[set[str]] = {
        "plan_id",
        "source_actor",
        "target_actor",
        "profile_id",
        "workspace_id",
        "object_ids",
        "operation_class",
        "dependencies",
        "policy_decision_ref",
        "retry_policy",
        "conflict_policy",
        "status",
        "user_explanation",
        "created_at",
        "updated_at",
    }
    controlled_fields: ClassVar[dict[str, set[str]]] = {"operation_class": SYNC_OPERATION_CLASSES, "status": SYNC_PLAN_STATUSES}
    list_fields: ClassVar[set[str]] = {"object_ids", "dependencies"}

    plan_id: str
    source_actor: str
    target_actor: str
    profile_id: str
    workspace_id: str
    object_ids: list[str]
    operation_class: str
    dependencies: list[str]
    policy_decision_ref: str
    retry_policy: str
    conflict_policy: str
    status: str
    user_explanation: str
    created_at: str
    updated_at: str
    last_error: str | None = None


@dataclass(slots=True)
class ConflictRecord(JsonContract):
    schema: ClassVar[str] = "sourceos.conflict-record/v1alpha1"
    required_fields: ClassVar[set[str]] = {
        "conflict_id",
        "object_id",
        "object_type",
        "workspace_id",
        "profile_id",
        "actors",
        "devices",
        "schema_version",
        "severity",
        "merge_policy",
        "user_explanation",
        "created_at",
    }
    controlled_fields: ClassVar[dict[str, set[str]]] = {"severity": CONFLICT_SEVERITIES}
    list_fields: ClassVar[set[str]] = {"actors", "devices"}

    conflict_id: str
    object_id: str
    object_type: str
    workspace_id: str
    profile_id: str
    actors: list[str]
    devices: list[str]
    schema_version: str
    severity: str
    merge_policy: str
    user_explanation: str
    created_at: str


@dataclass(slots=True)
class PolicyDecisionRecord(JsonContract):
    schema: ClassVar[str] = "sourceos.policy-decision/v1alpha1"
    required_fields: ClassVar[set[str]] = {
        "decision_id",
        "effect",
        "policy_id",
        "policy_version",
        "actor_id",
        "profile_id",
        "workspace_id",
        "rationale",
        "decided_at",
    }
    controlled_fields: ClassVar[dict[str, set[str]]] = {"effect": POLICY_EFFECTS}

    decision_id: str
    effect: str
    policy_id: str
    policy_version: str
    actor_id: str
    profile_id: str
    workspace_id: str
    rationale: str
    decided_at: str
    object_id: str | None = None


@dataclass(slots=True)
class IntegrityEventRecord(JsonContract):
    schema: ClassVar[str] = "sourceos.integrity-event/v1alpha1"
    required_fields: ClassVar[set[str]] = {"event_id", "event_type", "occurred_at", "summary"}

    event_id: str
    event_type: str
    occurred_at: str
    summary: str
    actor_id: str | None = None
    object_id: str | None = None
    device_id: str | None = None
    profile_id: str | None = None
    workspace_id: str | None = None
    schema_version: str | None = None
    policy_decision_ref: str | None = None


@dataclass(slots=True)
class AgentObjectTransactionRecord(JsonContract):
    schema: ClassVar[str] = "sourceos.agent-object-transaction/v1alpha1"
    required_fields: ClassVar[set[str]] = {
        "transaction_id",
        "actor_id",
        "workspace_id",
        "profile_id",
        "object_ids",
        "operation",
        "status",
        "policy_decision_ref",
        "created_at",
        "updated_at",
    }
    controlled_fields: ClassVar[dict[str, set[str]]] = {"operation": TRANSACTION_OPERATIONS, "status": TRANSACTION_STATUSES}
    list_fields: ClassVar[set[str]] = {"object_ids"}

    transaction_id: str
    actor_id: str
    workspace_id: str
    profile_id: str
    object_ids: list[str]
    operation: str
    status: str
    policy_decision_ref: str
    created_at: str
    updated_at: str


CONTRACT_TYPES: dict[str, type[JsonContract]] = {
    ProfileRecord.schema: ProfileRecord,
    DeviceTrustRecord.schema: DeviceTrustRecord,
    ActorRecord.schema: ActorRecord,
    SchemaContractRecord.schema: SchemaContractRecord,
    SourceObjectRecord.schema: SourceObjectRecord,
    SyncPlanRecord.schema: SyncPlanRecord,
    ConflictRecord.schema: ConflictRecord,
    PolicyDecisionRecord.schema: PolicyDecisionRecord,
    IntegrityEventRecord.schema: IntegrityEventRecord,
    AgentObjectTransactionRecord.schema: AgentObjectTransactionRecord,
}


def validate_contract(record: dict[str, Any]) -> dict[str, Any]:
    schema = record.get("schema")
    if not isinstance(schema, str):
        raise ContractError("record.schema is required")
    contract_type = CONTRACT_TYPES.get(schema)
    if contract_type is None:
        raise ContractError(f"unsupported contract schema: {schema}")
    return contract_type.validate_dict(record)


def to_json_dict(contract: JsonContract) -> dict[str, Any]:
    return contract.to_dict()
