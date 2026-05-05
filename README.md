# sourceos-syncd

SourceOS State Integrity daemon: local-first object, actor, schema, repair, provenance, and policy-governed replication substrate.

## Mission

`sourceos-syncd` is the reference substrate for SourceOS local-first state integrity. It should make state observable, explainable, policy-governed, repairable, attestable, and safe for agent use.

This repository is the canonical home for the SourceOS State Integrity Report and Index Lane model.

## Core concepts

- **State Integrity Report**: durable JSON health artifact for stateful daemons, indexes, sync engines, memory stores, and repair systems.
- **Index Lanes**: explicit operational classes for normal, priority, secure, ephemeral, memory, policy, audit, tombstone, migration, repair, and archive state.
- **Diagnosis layer**: interpreted health beside raw telemetry.
- **Repair plan**: non-destructive preview before any state mutation or purge.
- **Policy-native indexing**: PolicyFabric controls indexing, retention, replication, purge, and agent access.
- **Attested operations**: Lampstand preserves important state reports and repair actions as signed evidence.

## Specs

- [`docs/specs/sourceos-state-integrity-report.md`](docs/specs/sourceos-state-integrity-report.md)
- [`docs/specs/sourceos-index-lanes.md`](docs/specs/sourceos-index-lanes.md)

## Golden examples

- [`examples/health/healthy.snapshot.json`](examples/health/healthy.snapshot.json)
- [`examples/health/degraded.snapshot.json`](examples/health/degraded.snapshot.json)
- [`examples/health/repair-plan.json`](examples/health/repair-plan.json)

## Intended CLI contract

```bash
sourceos-syncd health snapshot
sourceos-syncd health explain
sourceos-syncd health verify
sourceos-syncd repair plan
sourceos-syncd repair apply --approved-plan ./repair-plan.json
sourceos-syncd repair rollback
```

The repo-level SourceOS contract should eventually expose equivalent shared commands:

```bash
sourceos health snapshot --json
sourceos health explain
sourceos health verify
sourceos repair plan
sourceos repair apply --approved-plan ./repair-plan.json
sourceos repair rollback
```

## Intended local HTTP contract

Local-only by default:

- `/healthz` liveness
- `/readyz` readiness
- `/statez` structured State Integrity Report
- `/metrics` Prometheus/OpenTelemetry export
- `/repairz` repair planning endpoint, disabled remotely unless policy explicitly allows it

## Estate integration targets

- `SocioProphet/policy-fabric`: policy decisions for indexing, retention, replication, purge, and agent access.
- `SocioProphet/agentplane`: trust gates before agent actions against state substrates.
- `SocioProphet/lampstand`: signed evidence, repair records, and incident timelines.
- `SocioProphet/memory-mesh`: memory-lane health, tombstones, staleness, and replay.
- `SocioProphet/smart-tree`: object graph freshness, repo index health, and structural churn.
- DeliveryExcellence stack: estate-wide health scoring, SLOs, release readiness, and regression tracking.

## First implementation target

The first implementation should produce and validate the golden examples, then expose `health snapshot`, `health explain`, and `repair plan` without destructive `repair apply`.
