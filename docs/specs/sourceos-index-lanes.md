# SourceOS Index Lanes

Status: draft v0.1
Owner: SourceOS
Scope: indexing, sync, memory, repair, provenance, and policy-governed local-first state.

## Purpose

SourceOS state must not be organized as one undifferentiated index. Local-first systems need explicit lanes with different latency, retention, privacy, replication, compaction, and repair behavior.

An index lane is an operational class of state. Lanes exist so SourceOS can prioritize critical work, protect sensitive data, preserve audit evidence, support lazy migrations, and recover without destructive rebuilds.

## Required lanes

### normal

Default searchable state.

Used for ordinary files, repo metadata, non-sensitive object graph entries, package metadata, and durable local objects.

Defaults:

- searchable: yes
- agent-visible: policy-gated
- replicated: policy-gated
- retention: standard
- compaction: opportunistic
- purge: policy-driven

### priority

Latency-sensitive or user-visible state.

Used for active user work, recent objects, security alerts, pending decisions, agent-critical working context, and boot-critical metadata.

Defaults:

- searchable: yes
- agent-visible: policy-gated
- replicated: policy-gated
- retention: short-to-standard depending on domain
- compaction: preemptive
- purge: conservative
- scheduling: preempts normal lane

### secure

Sensitive state requiring stricter access and redaction.

Used for secrets, credentials, private governance records, security-sensitive audit details, sensitive memory, and privileged local metadata.

Defaults:

- searchable: redacted or disabled unless policy allows
- agent-visible: denied by default
- replicated: denied by default
- retention: explicit policy only
- compaction: encrypted/checkpointed
- purge: audited
- samples in health reports: redacted

### ephemeral

Temporary session state.

Used for short-lived working context, command sessions, transient cache, speculative agent state, and UI/session intermediates.

Defaults:

- searchable: no or short-window only
- agent-visible: local session only
- replicated: no
- retention: bounded TTL
- compaction: usually unnecessary
- purge: aggressive

### memory

Agent and human memory substrate.

Used for working memory, long-term memory, embeddings, summaries, provenance links, memory tombstones, and confidence metadata.

Defaults:

- searchable: yes, with policy gates
- agent-visible: trust-gated
- replicated: policy-gated
- retention: explicit by memory class
- compaction: semantic and structural
- purge: tombstone-aware
- extra health: staleness, provenance, confidence, contradiction pressure

### policy

Governance state.

Used for policy decisions, grants, denials, retention classes, replication rules, indexing authorization, agent access decisions, and purge approvals.

Defaults:

- searchable: limited
- agent-visible: explain-only unless policy allows mutation
- replicated: explicit
- retention: audit-aligned
- compaction: conservative
- purge: rare and attested

### audit

Append-only evidence lane.

Used for state reports, repair decisions, policy decisions, attestation records, migration records, incident timelines, and operator actions.

Defaults:

- searchable: metadata yes, content policy-gated
- agent-visible: explain-only by default
- replicated: policy-gated
- retention: long
- compaction: append-only segment compaction only
- purge: exceptional and attested

### tombstone

Deletion lifecycle lane.

Used for delete requests, authorization records, tombstones, propagation status, purge eligibility, and deletion proofs.

Defaults:

- searchable: metadata only
- agent-visible: explain-only
- replicated: yes when object was replicated
- retention: until propagation and audit requirements are satisfied
- compaction: after proof
- purge: policy-authorized only

### migration

Schema and generation transition lane.

Used for lazy migrations, A/B store builds, old-generation compatibility, index rebuilds, and active pointer flips.

Defaults:

- searchable: no unless explicitly activated
- agent-visible: health only
- replicated: no unless needed for migration protocol
- retention: until migration complete and verified
- compaction: after cutover
- purge: after rollback window expires

### repair

Quarantine and reconstruction lane.

Used for corrupted objects, orphan records, failed checksum items, replay failures, dirty-open recovery, and safe repair staging.

Defaults:

- searchable: no
- agent-visible: no except diagnosis
- replicated: no until verified
- retention: until repair closeout
- compaction: after verification
- purge: after checkpoint and attestation

### archive

Cold durable state.

Used for infrequently used but retained objects, old reports, previous generations, and low-priority historical material.

Defaults:

- searchable: metadata first, content lazy-loaded
- agent-visible: policy-gated
- replicated: policy-gated
- retention: long
- compaction: high compression
- purge: retention-policy driven

## Lane metadata

Each lane must publish:

```json
{
  "name": "priority",
  "status": "active|dormant|degraded|repairing|retired",
  "sla": {
    "max_heartbeat_age_ms": 30000,
    "max_replay_lag_events": 0,
    "max_replay_lag_ms": 1000
  },
  "policy": {
    "indexing": "sourceos.index/priority",
    "retention": "sourceos.retention/priority",
    "replication": "sourceos.replication/local-first",
    "agent_access": "sourceos.agent/trust-gated"
  },
  "journal": {},
  "objects": {},
  "maintenance": {},
  "diagnosis": {}
}
```

## Scheduling rules

1. Priority lane preempts normal, archive, and migration work.
2. Secure lane work fails closed when PolicyFabric is unavailable.
3. Tombstone propagation preempts purge.
4. Repair lane work blocks readiness for affected stores until verification completes.
5. Migration lane may run lazily but must not block active reads unless schema compatibility is broken.
6. Audit lane must not be silently dropped during disk pressure; it must degrade explicitly.
7. Ephemeral lane is first to purge under pressure.
8. Archive lane is first to compact for storage recovery.

## Disk pressure behavior

| Pressure | Behavior |
| --- | --- |
| none | normal operation |
| watch | reduce speculative indexing; defer archive hydration |
| warning | pause low-priority ingestion; compact archive and normal lanes; purge eligible ephemeral state |
| critical | stop nonessential writes; preserve audit and tombstones; require policy-guided purge |

## Memory pressure behavior

| Pressure | Behavior |
| --- | --- |
| none | normal operation |
| watch | reduce batch sizes |
| warning | disable speculative embedding/indexing; lower cache ceilings |
| critical | stop background compaction; only priority, repair, and audit writes continue |

## Migration pattern

SourceOS supports A/B stores and lazy migrations:

1. Keep active generation online.
2. Build new generation in the migration lane.
3. Verify object count, journal replay, checksum, schema, and policy compatibility.
4. Flip active pointer atomically.
5. Keep rollback window open.
6. Retire old generation after attested success.

## Delete lifecycle

Deletion must be explicit:

1. delete requested
2. policy authorization checked
3. tombstone written
4. tombstone propagated to relevant peers
5. object hidden from normal search
6. object purged when policy allows
7. purge proof written to audit lane
8. tombstone compacted after retention window

## Agent trust contract

AgentPlane must not treat all lanes as equally trustworthy.

Agents may use a lane only when:

- lane diagnosis is healthy or explicitly accepted as degraded
- policy allows agent access
- replay lag is within lane SLA
- schema is compatible
- attestation state meets trust requirement
- secure lane redaction rules are honored

Agent actions against stale memory, failed policy, or repair/quarantine lanes should be blocked unless an explicit degraded-mode authorization exists.

## DeliveryExcellence scoring

Every lane contributes to estate health scoring:

- health status
- replay lag
- compaction debt
- purge debt
- repair debt
- policy denial rate
- disk/memory pressure behavior
- attestation coverage
- schema migration state

This lets SourceOS measure platform readiness by operating truth, not only repository activity.
