# SourceOS State Integrity Contracts

Canonical architecture: `SourceOS-Linux/sourceos-spec/docs/architecture/sourceos-state-integrity-layer.md`

This repository implements the first executable contract for SourceOS State Integrity. The current implementation lane is Python and standard-library-first. It provides State Integrity Report generation, diagnosis, verification, non-destructive repair planning, a filesystem-backed local store prototype, an append-only JSONL event log, registry persistence, and contract models for actors, schemas, objects, policy decisions, conflicts, events, profiles, devices, sync plans, workspace operations, operation tasks, and agent object transactions.

The next daemon phases should extend this baseline into full event-log, policy, profile, repair, service, and adapter subsystems without breaking the current JSON report contracts.

## Contract Principles

- Structured JSON is the stable integration boundary.
- Logs are evidence, not API contracts.
- Repair starts as preview/planning; apply paths require explicit policy and operator approval.
- Durable state, rebuildable state, and disposable state must be classified separately.
- Policy denials, conflicts, transport failures, degraded indexes, and repair-needed states must not collapse into generic errors.
- Agent writes must be attributable to registered actors.
- Downstream surfaces should consume reports/events/contracts, not scrape raw daemon logs.
- Read paths must not silently initialize, reset, or repair local state.

## Current CLI Commands

The current repo implementation exposes:

```bash
sourceos-syncd health snapshot
sourceos-syncd health snapshot --compact
sourceos-syncd health snapshot --store-root ./state --compact
sourceos-syncd health explain --file examples/health/healthy.snapshot.json
sourceos-syncd health verify --file examples/health/healthy.snapshot.json
sourceos-syncd repair plan --file examples/health/degraded.snapshot.json
```

The current commands are intentionally read-only or preview-only. `repair plan` emits a plan; it does not mutate state.

## Local Store CLI Commands

The filesystem-backed prototype adds explicit store commands:

```bash
sourceos-syncd store init --root ./state
sourceos-syncd store record --root ./state --event-type add --lane normal --object-id object:alpha --producer manual --payload-json '{}'
sourceos-syncd store put-record --root ./state --kind actors --record-id actor:agent-one --record-json '{"actor_id":"actor:agent-one","actor_type":"agent"}'
sourceos-syncd store get-record --root ./state --kind actors --record-id actor:agent-one
sourceos-syncd store list-records --root ./state --kind actors
```

Supported registry kinds:

- `profiles`
- `devices`
- `actors`
- `schemas`
- `objects`
- `indexes`
- `repair-reports`

## Local Store Layout

The MVP filesystem store uses this layout:

```text
<store-root>/
  manifest.json
  journal.jsonl
  profiles/
  devices/
  actors/
  schemas/
  objects/
  events/
  repair-reports/
  indexes/
  checkpoints/
  tmp/
```

Durable directories:

- `profiles`
- `devices`
- `actors`
- `schemas`
- `objects`
- `events`
- `repair-reports`

Rebuildable directories:

- `indexes`
- `checkpoints`

Disposable directories:

- `tmp`

## Contract Model Module

The contract model module is:

```text
src/sourceos_syncd/contracts.py
```

It provides standard-library-only dataclass contracts and validation for:

```text
sourceos.profile-record/v1alpha1
sourceos.device-record/v1alpha1
sourceos.actor-record/v1alpha1
sourceos.schema-record/v1alpha1
sourceos.object-record/v1alpha1
sourceos.sync-plan/v1alpha1
sourceos.conflict-record/v1alpha1
sourceos.policy-decision/v1alpha1
sourceos.integrity-event/v1alpha1
sourceos.agent-object-transaction/v1alpha1
sourceos.workspace-operation/v1alpha1
sourceos.operation-task/v1alpha1
```

Use `validate_contract(record)` to validate a JSON object by its `schema` field. Use the specific dataclass `from_dict()` helpers when callers know the expected type.

## Contract Fixtures

Fixtures live under:

```text
examples/contracts/
```

Current fixtures:

```text
profile.local-dev.json
device.local.json
actor.agent-one.json
schema.source-object-v1.json
object.alpha.json
sync-plan.alpha.json
conflict.alpha.json
policy.decision-review.json
event.object-alpha-created.json
agent-transaction.alpha.json
workspace-operation.alpha.json
operation-task.alpha.json
```

The contract test suite loads every fixture, validates it through the model registry, and round-trips each fixture through its dataclass model.

## Controlled Values

Actor types:

```text
human, app, agent, device, service, import_bridge, export_bridge, model_runtime, remote_relay
```

Actor capabilities:

```text
read, write, delete, merge, repair, migrate_schema, export, replicate
```

Trust levels:

```text
local, user, workspace, org, external, quarantined
```

Privacy classes:

```text
public, personal, work, confidential, regulated, secret
```

Sync visibility:

```text
local_only, profile, workspace, org, public
```

Retention classes:

```text
ephemeral, normal, retained, legal_hold
```

Object states:

```text
active, deleted, tombstoned, quarantined, conflicted
```

Sync operation classes:

```text
replicate, import, export, repair, migrate, delete, restore
```

Sync plan statuses:

```text
planned, blocked, running, failed, completed, cancelled
```

Conflict severities:

```text
info, warning, review_required, blocking
```

Policy effects:

```text
allow, deny, review_required
```

Agent transaction operations:

```text
create, update, delete, merge, repair, migrate
```

Agent transaction statuses:

```text
draft, proposed, approved, applied, rejected, reverted
```

Workspace operation types:

```text
sync.operation.enqueue, sync.operation.replay, sync.operation.reconcile, sync.conflict.detect, sync.conflict.resolve, sync.repair.apply, sync.tombstone.apply, sync.checkpoint.write
```

Decision card options:

```text
merge, fork, skip
```

Device states:

```text
trusted, untrusted, revoked, quarantined
```

Profile classes:

```text
personal, work, client, air_gapped, lab, public_open_source
```

## Current Registry Record Schemas

Registry writes assign default schemas when a record does not already provide one:

```text
profiles       -> sourceos.profile-record/v1alpha1
devices        -> sourceos.device-record/v1alpha1
actors         -> sourceos.actor-record/v1alpha1
schemas        -> sourceos.schema-record/v1alpha1
objects        -> sourceos.object-record/v1alpha1
indexes        -> sourceos.index-record/v1alpha1
repair-reports -> sourceos.repair-report/v1alpha1
```

Registry records are JSON objects written atomically as individual files. The MVP intentionally avoids opaque database behavior until the contract is stable.

## Intended CLI Commands

The README tracks the intended larger CLI surface:

```bash
sourceos-syncd health snapshot
sourceos-syncd health explain
sourceos-syncd health verify
sourceos-syncd repair plan
sourceos-syncd repair apply --approved-plan ./repair-plan.json
sourceos-syncd repair rollback
sourceos-syncd events explain
sourceos-syncd events coalesce
sourceos-syncd events verify
```

Apply/rollback and event commands are not the current safe baseline unless implemented with tests and policy gates.

## Expected SourceOS Wrapper

`sourceos-devtools` should eventually expose equivalent shared commands:

```bash
sourceos health snapshot --json
sourceos health explain
sourceos health verify
sourceos repair plan
sourceos repair apply --approved-plan ./repair-plan.json
sourceos repair rollback
sourceos events explain
sourceos events coalesce
sourceos events verify
```

The broader `sourceos sync ...` surface can wrap this daemon after object registry, actor registry, schema registry, and sync-plan primitives exist.

## Current Model Families

The current Python implementation defines these contract families:

- State Integrity Report v1alpha1
- Repair Plan v1alpha1
- identity and collection metadata
- runtime heartbeat/replay timestamps
- store generation/checksum/migration metadata
- lane health, objects, journal, and maintenance metadata
- pipeline counters
- resource pressure
- policy decision counters
- invariants
- diagnosis
- controls
- attestation
- local store metadata
- append-only journal events
- registry records
- typed contract dataclasses and validators

## Next Model Families

The next implementation phase should add deeper behavior around the now-defined contracts:

- policy decision adapter
- schema registry validation and migrations
- object registry validation against schema contracts
- sync plan execution state
- conflict resolution reports
- repair reports tied to durable/rebuildable/disposable state
- profile and device trust lifecycle
- agent transaction review/apply/revert workflow

## MVP Persistence Boundary

The next implementation phase should deepen persistence in this order:

1. formal local config/profile/device discovery
2. stronger append-only event log checksums
3. actor registry validation
4. schema registry validation and migrations
5. object registry validation
6. derived index classification and rebuild reports
7. dry-run repair of a derived index
8. policy decision adapter
9. workspace/file object adapter
10. agent transaction path

## Non-Goals for First Cut

- no cloud replication
- no hidden repair
- no destructive import/export
- no anonymous agent writes
- no log-scraping integrations
- no silent schema drift
- no split-brain implementation language lane without an explicit migration decision
