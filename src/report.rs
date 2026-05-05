use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use crate::models::HealthState;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum RepairMode {
    DryRun,
    Apply,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum RepairRisk {
    SafeDerivedStateRebuild,
    ReviewRequired,
    PolicyBlocked,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RepairReport {
    pub report_id: String,
    pub mode: RepairMode,
    pub generated_at: DateTime<Utc>,
    pub health_before: HealthState,
    pub health_after: Option<HealthState>,
    pub affected_objects: u64,
    pub preserved_durable_objects: u64,
    pub rebuilt_indexes: u64,
    pub quarantined_objects: u64,
    pub unresolved_conflicts: u64,
    pub policy_decisions: Vec<String>,
    pub risk: RepairRisk,
    pub summary: String,
    pub next_action: String,
}

pub fn sample_repair_report(now: DateTime<Utc>, mode: RepairMode) -> RepairReport {
    let (health_after, summary, next_action) = match mode {
        RepairMode::DryRun => (
            None,
            "Dry-run completed. No durable state was modified.".to_string(),
            "Review this report before running a scoped apply operation.".to_string(),
        ),
        RepairMode::Apply => (
            Some(HealthState::Clean),
            "Apply completed against sample state. No durable user objects were modified.".to_string(),
            "Run `sourceos sync status` to verify current health.".to_string(),
        ),
    };

    RepairReport {
        report_id: format!("repair:{}", now.timestamp()),
        mode,
        generated_at: now,
        health_before: HealthState::RepairRecommended,
        health_after,
        affected_objects: 0,
        preserved_durable_objects: 0,
        rebuilt_indexes: 0,
        quarantined_objects: 0,
        unresolved_conflicts: 0,
        policy_decisions: vec![],
        risk: RepairRisk::SafeDerivedStateRebuild,
        summary,
        next_action,
    }
}
