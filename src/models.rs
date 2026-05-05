use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum HealthState {
    Clean,
    Degraded,
    Conflicted,
    PolicyBlocked,
    OfflineLocalOnly,
    RepairRecommended,
    DaemonUnavailable,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum DurabilityClass {
    Durable,
    Rebuildable,
    Disposable,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ActorType {
    Human,
    App,
    Agent,
    Device,
    Service,
    ImportBridge,
    ExportBridge,
    ModelRuntime,
    RemoteRelay,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ActorCapability {
    Read,
    Write,
    Delete,
    Merge,
    Repair,
    MigrateSchema,
    Export,
    Replicate,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum TrustLevel {
    Local,
    User,
    Workspace,
    Org,
    External,
    Quarantined,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum PrivacyClass {
    Public,
    Personal,
    Work,
    Confidential,
    Regulated,
    Secret,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum SyncVisibility {
    LocalOnly,
    Profile,
    Workspace,
    Org,
    Public,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum RetentionClass {
    Ephemeral,
    Normal,
    Retained,
    LegalHold,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ObjectState {
    Active,
    Deleted,
    Tombstoned,
    Quarantined,
    Conflicted,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum SyncOperationClass {
    Replicate,
    Import,
    Export,
    Repair,
    Migrate,
    Delete,
    Restore,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum SyncPlanStatus {
    Planned,
    Blocked,
    Running,
    Failed,
    Completed,
    Cancelled,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ConflictSeverity {
    Info,
    Warning,
    ReviewRequired,
    Blocking,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum PolicyDecisionEffect {
    Allow,
    Deny,
    ReviewRequired,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProfileRef {
    pub profile_id: String,
    pub display_name: String,
    pub profile_class: String,
    pub health: HealthState,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeviceRef {
    pub device_id: String,
    pub display_name: String,
    pub trust_level: TrustLevel,
    pub revoked_at: Option<DateTime<Utc>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ActorRecord {
    pub actor_id: String,
    pub actor_type: ActorType,
    pub display_name: String,
    pub identity_id: String,
    pub workspace_scope: Vec<String>,
    pub profile_scope: Vec<String>,
    pub capabilities: Vec<ActorCapability>,
    pub trust_level: TrustLevel,
    pub policy_subject: String,
    pub signing_key_ref: String,
    pub created_at: DateTime<Utc>,
    pub revoked_at: Option<DateTime<Utc>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SourceObject {
    pub object_id: String,
    pub object_type: String,
    pub schema_version: String,
    pub workspace_id: String,
    pub profile_id: String,
    pub owner_identity: String,
    pub created_by_actor: String,
    pub last_modified_by_actor: String,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
    pub privacy_class: PrivacyClass,
    pub sync_visibility: SyncVisibility,
    pub retention_class: RetentionClass,
    pub policy_tags: Vec<String>,
    pub provenance: Vec<String>,
    pub content_hash: Option<String>,
    pub state: ObjectState,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SchemaContract {
    pub object_type: String,
    pub schema_version: String,
    pub core_fields: Vec<String>,
    pub extension_namespaces: Vec<String>,
    pub migration_policy: String,
    pub downgrade_behavior: String,
    pub conflict_policy: String,
    pub tombstone_policy: String,
    pub sync_visibility: SyncVisibility,
    pub encryption_classification: String,
    pub retention_classification: RetentionClass,
    pub indexing_classification: DurabilityClass,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SyncPlan {
    pub plan_id: String,
    pub source_actor: String,
    pub target_actor: String,
    pub profile_id: String,
    pub workspace_id: String,
    pub object_ids: Vec<String>,
    pub operation_class: SyncOperationClass,
    pub dependencies: Vec<String>,
    pub policy_decision_ref: String,
    pub retry_policy: String,
    pub conflict_policy: String,
    pub status: SyncPlanStatus,
    pub last_error: Option<String>,
    pub user_explanation: String,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConflictRecord {
    pub conflict_id: String,
    pub object_id: String,
    pub object_type: String,
    pub workspace_id: String,
    pub profile_id: String,
    pub actors: Vec<String>,
    pub devices: Vec<String>,
    pub schema_version: String,
    pub severity: ConflictSeverity,
    pub merge_policy: String,
    pub user_explanation: String,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolicyDecision {
    pub decision_id: String,
    pub effect: PolicyDecisionEffect,
    pub policy_id: String,
    pub policy_version: String,
    pub actor_id: String,
    pub object_id: Option<String>,
    pub profile_id: String,
    pub workspace_id: String,
    pub rationale: String,
    pub decided_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IntegrityEvent {
    pub event_id: String,
    pub event_type: String,
    pub occurred_at: DateTime<Utc>,
    pub actor_id: Option<String>,
    pub object_id: Option<String>,
    pub device_id: Option<String>,
    pub profile_id: Option<String>,
    pub workspace_id: Option<String>,
    pub schema_version: Option<String>,
    pub policy_decision_ref: Option<String>,
    pub summary: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StateStatus {
    pub daemon: String,
    pub daemon_available: bool,
    pub version: String,
    pub generated_at: DateTime<Utc>,
    pub active_profile: ProfileRef,
    pub active_device: DeviceRef,
    pub active_workspace_id: String,
    pub health: HealthState,
    pub durable_object_count: u64,
    pub rebuildable_index_count: u64,
    pub disposable_state_count: u64,
    pub conflict_count: u64,
    pub policy_block_count: u64,
    pub repair_recommendation_count: u64,
}

pub fn sample_status(now: DateTime<Utc>) -> StateStatus {
    StateStatus {
        daemon: "sourceos-syncd".to_string(),
        daemon_available: true,
        version: env!("CARGO_PKG_VERSION").to_string(),
        generated_at: now,
        active_profile: ProfileRef {
            profile_id: "profile:local-dev".to_string(),
            display_name: "Local Development".to_string(),
            profile_class: "lab".to_string(),
            health: HealthState::Clean,
        },
        active_device: DeviceRef {
            device_id: "device:local".to_string(),
            display_name: "Local SourceOS device".to_string(),
            trust_level: TrustLevel::Local,
            revoked_at: None,
        },
        active_workspace_id: "workspace:default".to_string(),
        health: HealthState::Clean,
        durable_object_count: 0,
        rebuildable_index_count: 0,
        disposable_state_count: 0,
        conflict_count: 0,
        policy_block_count: 0,
        repair_recommendation_count: 0,
    }
}
