# SourceOS State Integrity Report

Status: draft v0.1
Owner: SourceOS
Scope: local-first daemons, indexes, sync engines, memory stores, policy engines, agent runtimes, and repair tools.

## Purpose

The SourceOS State Integrity Report is the canonical health, diagnosis, and repair contract for stateful SourceOS components.

The report exists because logs and metrics are insufficient for local-first infrastructure. A daemon must be able to explain what state it owns, how fresh that state is, which invariants hold, which policies control it, what repair is safe, and whether agents may trust it.

The report is not a crash dump. It is an operating artifact.

## Design principles

1. No opaque telemetry. Every raw counter or bitfield must have a decoded form, unit, scope, and stability contract.
2. Separate telemetry from diagnosis. Machines need counters; operators and agents need interpreted health.
3. Treat state as a replayable pipeline. Requested, accepted, journaled, applied, replayed, skipped, failed, and repaired are different states.
4. Treat deletion as a lifecycle. Delete means requested, authorized, tombstoned, propagated, compacted, purged, and attested.
5. Treat compaction and purge as separate control loops. Compaction optimizes layout. Purge enforces retention and storage policy.
6. Prefer lazy migration. Old store generations may remain online until verified, compacted, rewritten, or retired.
7. Make repair non-destructive by default. Every destructive operation requires an explicit plan, checkpoint, policy authorization, and rollback story.
8. Measure health-of-health. A report must disclose missing, redacted, timed-out, or permission-denied fields.
9. Sign important state. Critical reports should be attestable by Lampstand and consumable by AgentPlane.
10. Close the loop. Every degraded diagnosis should map to a safe controller action or an explicit manual decision.

## Required top-level shape

```json
{
  "schema": "sourceos.state-integrity-report/v1alpha1",
  "generated_at": "2026-05-04T17:15:17Z",
  "identity": {},
  "collection": {},
  "runtime": {},
  "stores": [],
  "lanes": [],
  "pipeline": {},
  "resources": {},
  "policy": {},
  "invariants": [],
  "diagnosis": {},
  "controls": [],
  "attestation": {}
}
```

## Identity

Identity binds the report to code, process, host, and build provenance.

Required fields:

```json
{
  "component": "sourceos-syncd",
  "repo": "SourceOS-Linux/sourceos-syncd",
  "pid": 675,
  "process_name": "sourceos-syncd",
  "node_id_hash": "sha256:...",
  "boot_id": "...",
  "version": "0.1.0",
  "commit": "...",
  "build_provenance": "local-dev|ci|release",
  "platform": "linux|macos|windows",
  "service_manager": "systemd|launchd|windows-service|manual"
}
```

No report should expose a raw machine identifier unless policy explicitly allows it. Use a stable local hash by default.

## Collection status

A clean-looking report can still be false if collection silently failed. Every report must disclose its own completeness.

```json
{
  "status": "complete|partial|failed",
  "duration_ms": 14,
  "errors": [],
  "redacted_fields": ["lanes.secure.samples"],
  "permission_denied_fields": [],
  "timed_out_fields": [],
  "unavailable_fields": []
}
```

Sentinel values such as `-1`, `null`, or `unknown` must include a reason code: `not_applicable`, `permission_denied`, `redacted`, `collector_timeout`, `unsupported_platform`, or `not_yet_initialized`.

## Runtime lifecycle

Do not collapse every lifecycle clock into uptime. Local-first state has phases.

```json
{
  "process_started_at": "2026-05-04T12:00:00Z",
  "runtime_ready_at": "2026-05-04T12:00:03Z",
  "store_opened_at": "2026-05-04T12:00:04Z",
  "replay_started_at": "2026-05-04T12:00:04Z",
  "replay_completed_at": "2026-05-04T12:00:07Z",
  "first_heartbeat_at": "2026-05-04T12:00:08Z",
  "last_heartbeat_at": "2026-05-04T17:14:57Z",
  "last_clean_shutdown_at": "2026-05-03T14:47:37Z",
  "last_dirty_open_at": null
}
```

## Stores

A store is a durable state container. Stores may be active, dormant, migration-only, retired, quarantined, or rebuilding.

```json
{
  "name": "content-store-a",
  "role": "active|shadow|migration|archive|repair|retired",
  "backend": "sqlite|sled|rocksdb|tantivy|filesystem|custom",
  "schema_version": "1.0.0",
  "created_by_version": "0.1.0",
  "runtime_version": "0.1.1",
  "previous_runtime_version": "0.1.0",
  "migration_state": "none|pending|lazy|running|complete|failed|rollback_available",
  "active_generation": 42,
  "last_known_good_generation": 41,
  "shadow_present": true,
  "manifest_present": true,
  "checksum_state": "verified|unverified|mismatch|unsupported"
}
```

## Flags

Every numeric bitfield must expose raw, hex, and decoded values.

```json
{
  "flags_raw": 100664130,
  "flags_hex": "0x6000342",
  "flags_decoded": [
    "LANE_CONTENT",
    "LANE_USER_VISIBLE",
    "STORE_JOURNALED",
    "STORE_SHADOWED",
    "COMPACTION_ENABLED"
  ]
}
```

Flag registries must be versioned. Unknown bits are diagnosis warnings, not silently ignored values.

## Pipeline accounting

SourceOS state changes flow through explicit lifecycle states.

```json
{
  "add": {
    "external_requested": 157,
    "internal_generated": 2,
    "accepted": 159,
    "journaled": 159,
    "applied": 159,
    "deduped": 0,
    "replayed": 0,
    "skipped": 0,
    "failed": 0
  },
  "update": {
    "external_requested": 3263,
    "internal_generated": 2207,
    "accepted": 5470,
    "journaled": 3263,
    "applied": 5470,
    "deduped": 0,
    "replayed": 2207,
    "skipped": 0,
    "failed": 0
  },
  "delete": {
    "external_requested": 165,
    "authorized": 165,
    "tombstoned": 165,
    "journaled": 308,
    "propagated": 154,
    "purged": 0,
    "failed": 0
  }
}
```

Processed counts may exceed requested counts when replay, fan-out, derived updates, or internal maintenance occur. Reports must make that explicit.

## Journal

Journal health must include both count and size. Many small segments and a few huge segments are different failure modes.

```json
{
  "segment_count": 5,
  "total_bytes": 166228,
  "max_segment_bytes": 166228,
  "oldest_unapplied_event_age_ms": 0,
  "replay_lag_events": 0,
  "replay_lag_bytes": 0,
  "replay_throughput_events_per_sec": 1200,
  "replay_eta_ms": 0,
  "checksum_state": "verified"
}
```

## Maintenance

Maintenance is split into global and lane-local control loops.

Compaction is lane-local and performance-driven.
Purge is global and policy-driven.
Repair is invariant-driven.
Verification is evidence-driven.

```json
{
  "last_compact_started_at": "2026-05-03T14:47:04Z",
  "last_compact_completed_at": "2026-05-03T14:47:38Z",
  "last_compact_duration_ms": 34000,
  "compaction_debt": "none|low|moderate|high|critical",
  "last_purge_started_at": "2026-03-15T09:00:00Z",
  "last_purge_completed_at": "2026-03-15T09:00:02Z",
  "purge_debt": "none|low|moderate|high|critical",
  "last_repair_at": null,
  "repair_debt": "none"
}
```

## Resources

Resource telemetry must drive backpressure and maintenance decisions.

```json
{
  "disk": {
    "filesystem": "btrfs|ext4|apfs|ntfs|unknown",
    "free_bytes": 24307728384,
    "total_bytes": 148315832320,
    "free_ratio": 0.164,
    "pressure": "none|watch|warning|critical"
  },
  "memory": {
    "total_gb": 8,
    "budget_mb": 256,
    "pressure": "none|watch|warning|critical"
  }
}
```

SourceOS must behave well on modest machines. Indexing, compaction, and replay must be budgeted.

## Policy

State health is inseparable from governance.

```json
{
  "policy_engine": "policy-fabric",
  "policy_version": "...",
  "indexing_policy": "sourceos.index/default",
  "retention_policy": "sourceos.retention/local-first-default",
  "replication_policy": "sourceos.replication/local-only",
  "agent_access_policy": "sourceos.agent/trust-gated",
  "policy_decisions": {
    "allowed": 1844,
    "denied": 12,
    "redacted": 7,
    "deferred": 0
  }
}
```

Policy-denied objects are not noise. Rising denial counts indicate governance friction and should be visible.

## Invariants

Invariants convert telemetry into verifiable promises.

Examples:

```json
[
  {
    "id": "journal.no_unapplied_events_when_ready",
    "status": "pass|warn|fail",
    "severity": "info|warning|error|critical",
    "evidence": { "replay_lag_events": 0 },
    "remediation": "run_replay"
  },
  {
    "id": "store.shadow_matches_active_generation",
    "status": "pass",
    "evidence": { "active_generation": 42, "shadow_generation": 42 },
    "remediation": "rebuild_shadow"
  }
]
```

Minimum invariant families:

- journal integrity
- replay completeness
- shadow/checkpoint validity
- schema compatibility
- dirty-open recovery
- tombstone propagation
- purge authorization
- disk pressure
- heartbeat freshness
- policy availability
- attestation validity

## Diagnosis

Diagnosis is the interpreted layer.

```json
{
  "status": "healthy|degraded|stale|repairing|unsafe|unknown",
  "severity": "info|warning|error|critical",
  "summary": "Content lane has moderate compaction debt; priority lane is healthy.",
  "causes": ["journal.segment_count_above_target"],
  "affected_lanes": ["content"],
  "affected_domains": ["repo-index", "agent-memory"],
  "safe_actions": ["compact_content_lane", "purge_preview"],
  "blocked_actions": ["destructive_purge_without_policy_grant"]
}
```

## Controls

Every degraded diagnosis should map to a controller or manual decision.

| Condition | Control |
| --- | --- |
| Heartbeat stale | restart, degrade readiness, alert |
| Journal lag high | replay, throttle producers, split lanes |
| Priority lane lagging | preempt normal lane work |
| Disk pressure rising | compact, purge eligible objects, pause ingestion |
| Dirty open detected | verify before ready |
| Schema drift | lazy migration, compatibility mode, rebuild lane |
| Policy engine unavailable | fail closed for sensitive lanes |
| Agent memory stale | block unsafe agent action |
| Repair failed | quarantine lane, preserve evidence |

## Attestation

Critical reports should be signed and preserved.

```json
{
  "signed": true,
  "signer": "lampstand",
  "key_id": "sourceos-local-node",
  "algorithm": "ed25519",
  "signature": "...",
  "evidence_uri": "lampstand://..."
}
```

Unsigned reports are acceptable in local development but must be clearly marked.

## CLI contract

Every daemon adopting this spec should provide:

```bash
sourceos health snapshot --json
sourceos health explain
sourceos health verify
sourceos repair plan
sourceos repair apply --approved-plan ./repair-plan.json
sourceos repair rollback
```

Daemon-local commands may be prefixed, for example:

```bash
sourceos-syncd health snapshot
sourceos-syncd health explain
sourceos-syncd repair plan
```

## HTTP contract

Local-only by default:

- `/healthz` liveness
- `/readyz` readiness
- `/statez` structured state report
- `/metrics` OpenTelemetry/Prometheus metrics
- `/repairz` repair planning endpoint, disabled remotely unless policy allows it

## Integration map

- `sourceos-syncd`: first implementation and canonical schema home.
- `policy-fabric`: indexing, retention, replication, purge, and agent-access decisions.
- `agentplane`: substrate trust checks before agent action.
- `lampstand`: signed evidence, incident timelines, and repair attestations.
- `memory-mesh`: memory lane health, tombstones, replay, and staleness.
- `smart-tree`: object graph freshness, repo index health, and structural churn.
- `deliveryexcellence`: estate-wide scorecards, SLOs, release readiness, and regression tracking.

## Definition of done for v1

1. JSON schema published.
2. Golden example reports committed.
3. CLI snapshot/explain/verify implemented in `sourceos-syncd`.
4. Repair plan format implemented without destructive apply.
5. PolicyFabric hook stubbed.
6. Lampstand attestation stubbed.
7. AgentPlane trust gate documented.
8. DeliveryExcellence ingestion issue opened.
