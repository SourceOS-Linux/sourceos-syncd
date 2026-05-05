# SourceOS State Integrity Contracts

Canonical architecture: `SourceOS-Linux/sourceos-spec/docs/architecture/sourceos-state-integrity-layer.md`

This repository implements the first executable contract for SourceOS State Integrity. The current implementation lane is Python and standard-library-first. It provides State Integrity Report generation, diagnosis, verification, non-destructive repair planning, a filesystem-backed local store prototype, an append-only JSONL event log, and registry persistence for early actor/schema/object/profile/device state.

The next daemon phases should extend this baseline into full actor, schema, object, event-log, policy, profile, and repair subsystems without breaking the current JSON report contracts.

## Contract Principles

- Structured JSON is the stable integration boundary.
- Logs are evidence, not API contracts.
- Repair starts as preview/planning; apply paths require explicit policy and operator approval.
- Durable state, rebuildable state, and disposable state must be classified separately.
- Policy denials, conflicts, transport failures, degraded indexes, and repair-needed states must not collapse into generic errors.
- Agent writes must eventually be attributable to registered actors.
- Downstream surfaces should consume reports/events, not scrape raw daemon logs.
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

## Next Model Families

The next implementation phase should add first-class contracts for:

- richer actor records
- source objects
- schema contracts
- sync plans
- conflict records
- policy decisions
- canonical integrity events
- repair reports tied to durable/rebuildable/disposable state
- profile and device trust records
- agent object transactions

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
