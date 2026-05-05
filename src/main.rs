use anyhow::{bail, Result};
use chrono::Utc;
use clap::{Parser, Subcommand};
use serde::Serialize;
use sourceos_syncd::models::{sample_status, ConflictRecord, HealthState, IntegrityEvent, SchemaContract, SyncPlan};
use sourceos_syncd::report::{sample_repair_report, RepairMode};

#[derive(Debug, Parser)]
#[command(name = "sourceos-syncd")]
#[command(about = "SourceOS State Integrity daemon and CLI contract")]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Debug, Subcommand)]
enum Command {
    /// Print current state health.
    Status {
        /// Emit JSON. Currently JSON is the stable contract and default output.
        #[arg(long, default_value_t = true)]
        json: bool,
    },
    /// Run non-destructive health checks.
    Doctor {
        /// Emit JSON. Currently JSON is the stable contract and default output.
        #[arg(long, default_value_t = true)]
        json: bool,
    },
    /// Explain a SourceOS object by id.
    Explain {
        object: String,
        #[arg(long, default_value_t = true)]
        json: bool,
    },
    /// List sync plans.
    Plans {
        #[arg(long, default_value_t = true)]
        json: bool,
    },
    /// List registered actors.
    Actors {
        #[arg(long, default_value_t = true)]
        json: bool,
    },
    /// List schema contracts.
    Schemas {
        #[arg(long, default_value_t = true)]
        json: bool,
    },
    /// List conflicts.
    Conflicts {
        #[arg(long, default_value_t = true)]
        json: bool,
    },
    /// Produce or apply a scoped repair report.
    Repair {
        #[arg(long)]
        dry_run: bool,
        #[arg(long)]
        apply: bool,
        #[arg(long, default_value_t = true)]
        json: bool,
    },
    /// List profiles.
    Profiles {
        #[arg(long, default_value_t = true)]
        json: bool,
    },
    /// List trusted devices.
    Devices {
        #[arg(long, default_value_t = true)]
        json: bool,
    },
    /// Export a workspace, profile, or object bundle. Stub only.
    Export {
        target: String,
        #[arg(long, default_value_t = true)]
        json: bool,
    },
    /// Import a bundle. Stub only.
    Import {
        bundle: String,
        #[arg(long, default_value_t = true)]
        json: bool,
    },
}

#[derive(Debug, Serialize)]
struct EmptyList<T: Serialize> {
    generated_at: chrono::DateTime<Utc>,
    items: Vec<T>,
}

#[derive(Debug, Serialize)]
struct ExplainResponse {
    generated_at: chrono::DateTime<Utc>,
    object_id: String,
    supported: bool,
    health: HealthState,
    explanation: String,
    next_action: String,
}

#[derive(Debug, Serialize)]
struct StubOperationResponse {
    generated_at: chrono::DateTime<Utc>,
    operation: String,
    target: String,
    supported: bool,
    explanation: String,
    next_action: String,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Command::Status { .. } => print_json(&sample_status(Utc::now())),
        Command::Doctor { .. } => print_json(&doctor_response()),
        Command::Explain { object, .. } => print_json(&ExplainResponse {
            generated_at: Utc::now(),
            object_id: object,
            supported: false,
            health: HealthState::DaemonUnavailable,
            explanation: "Object registry persistence is not implemented yet; this command currently validates the stable response contract.".to_string(),
            next_action: "Implement the object registry and event log MVP, then resolve object ids through durable local state.".to_string(),
        }),
        Command::Plans { .. } => print_json(&EmptyList::<SyncPlan> {
            generated_at: Utc::now(),
            items: vec![],
        }),
        Command::Actors { .. } => print_json(&EmptyList::<sourceos_syncd::models::ActorRecord> {
            generated_at: Utc::now(),
            items: vec![],
        }),
        Command::Schemas { .. } => print_json(&EmptyList::<SchemaContract> {
            generated_at: Utc::now(),
            items: vec![],
        }),
        Command::Conflicts { .. } => print_json(&EmptyList::<ConflictRecord> {
            generated_at: Utc::now(),
            items: vec![],
        }),
        Command::Repair { dry_run, apply, .. } => {
            if dry_run && apply {
                bail!("choose only one repair mode: --dry-run or --apply");
            }
            let mode = if apply { RepairMode::Apply } else { RepairMode::DryRun };
            print_json(&sample_repair_report(Utc::now(), mode))
        }
        Command::Profiles { .. } => print_json(&vec![sample_status(Utc::now()).active_profile]),
        Command::Devices { .. } => print_json(&vec![sample_status(Utc::now()).active_device]),
        Command::Export { target, .. } => print_json(&StubOperationResponse {
            generated_at: Utc::now(),
            operation: "export".to_string(),
            target,
            supported: false,
            explanation: "Export bundles are not implemented yet; this command reserves the contract.".to_string(),
            next_action: "Implement signed export bundles after object registry, policy decisions, and profile boundaries exist.".to_string(),
        }),
        Command::Import { bundle, .. } => print_json(&StubOperationResponse {
            generated_at: Utc::now(),
            operation: "import".to_string(),
            target: bundle,
            supported: false,
            explanation: "Import bundles are not implemented yet; this command reserves the contract.".to_string(),
            next_action: "Implement import dry-run before any apply path is added.".to_string(),
        }),
    }
}

fn doctor_response() -> Vec<IntegrityEvent> {
    vec![IntegrityEvent {
        event_id: format!("event:{}", Utc::now().timestamp()),
        event_type: "sync.doctor.completed".to_string(),
        occurred_at: Utc::now(),
        actor_id: Some("actor:local-cli".to_string()),
        object_id: None,
        device_id: Some("device:local".to_string()),
        profile_id: Some("profile:local-dev".to_string()),
        workspace_id: Some("workspace:default".to_string()),
        schema_version: None,
        policy_decision_ref: None,
        summary: "Doctor completed against stub state. Durable state was not modified.".to_string(),
    }]
}

fn print_json<T: Serialize>(value: &T) -> Result<()> {
    println!("{}", serde_json::to_string_pretty(value)?);
    Ok(())
}
