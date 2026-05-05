# sourceos-syncd

SourceOS State Integrity daemon: local-first object, actor, schema, repair, provenance, and policy-governed replication substrate.

## Mission

`sourceos-syncd` is the reference substrate for SourceOS local-first state integrity. It should make state observable, explainable, policy-governed, repairable, attestable, and safe for agent use.

This repository is the canonical home for the SourceOS State Integrity Report, Index Lane model, and telemetry signal-control doctrine.

## Core concepts

- **State Integrity Report**: durable JSON health artifact for stateful daemons, indexes, sync engines, memory stores, and repair systems.
- **Index Lanes**: explicit operational classes for normal, priority, secure, ephemeral, memory, policy, audit, tombstone, migration, repair, and archive state.
- **Diagnosis layer**: interpreted health beside raw telemetry.
- **Repair plan**: non-destructive preview before any state mutation or purge.
- **Policy-native indexing**: PolicyFabric controls indexing, retention, replication, purge, and agent access.
- **Attested operations**: Lampstand preserves important state reports and repair actions as signed evidence.
- **Telemetry signal control**: raw logs are evidence, not the product; expected policy blocks are classified correctly and duplicate noise is coalesced.
- **Operator narrative**: SourceOS explains what happened, why policy acted, what risk remains, and what action is required.

## Specs

- [`docs/specs/sourceos-state-integrity-report.md`](docs/specs/sourceos-state-integrity-report.md)
- [`docs/specs/sourceos-index-lanes.md`](docs/specs/sourceos-index-lanes.md)
- [`docs/telemetry-noise-control-spec.md`](docs/telemetry-noise-control-spec.md)
- [`docs/canonical-event-envelope.md`](docs/canonical-event-envelope.md)
- [`docs/implementation-roadmap.md`](docs/implementation-roadmap.md)

## JSON Schemas

- [`schemas/sourceos.state-integrity-report.v1alpha1.schema.json`](schemas/sourceos.state-integrity-report.v1alpha1.schema.json)
- [`schemas/sourceos.repair-plan.v1alpha1.schema.json`](schemas/sourceos.repair-plan.v1alpha1.schema.json)

The runtime validator is standard-library-only today; the schemas are the canonical external contract for downstream validators, SDKs, dashboards, and cross-repo integrations.

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
sourceos-syncd events explain
sourceos-syncd events coalesce
sourceos-syncd events verify
```

The repo-level SourceOS contract should eventually expose equivalent shared commands:

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

## Intended local HTTP contract

Local-only by default:

- `/healthz` liveness
- `/readyz` readiness
- `/statez` structured State Integrity Report
- `/events` canonical event stream, privacy-tiered by caller capability
- `/events/{id}` canonical event with evidence references
- `/events/{id}/explain` human operator narrative
- `/metrics` Prometheus/OpenTelemetry export
- `/repairz` repair planning endpoint, disabled remotely unless policy explicitly allows it

## Telemetry doctrine

SourceOS must not dump raw subsystem logs as the operator experience. Low-level logs remain immutable evidence. The default product surface is a canonical, coalesced, causally linked event with a privacy-preserving human explanation.

Required behaviors:

- Expected sandbox or capability denials render as `notice` and `blocked_expected`, not as false `error` events.
- Repeated identical records collapse into one event with `count`, `first_seen`, `last_seen`, and evidence samples.
- Redaction preserves causal structure: actor, target class, policy rule, and outcome remain understandable.
- Local-first trust verification is the baseline; network trust lookup must be explicit and policy-authorized.
- Analytics, hardware/UI diagnostics, and developer traces are separate lanes and suppressed from default security/operator views.

## Estate integration targets

- `SocioProphet/policy-fabric`: policy decisions for indexing, retention, replication, purge, agent access, telemetry outcomes, and explanation codes.
- `SocioProphet/agentplane`: trust gates before agent actions against state substrates and process/agent lineage traces.
- `SocioProphet/lampstand`: signed evidence, repair records, event attestations, and incident timelines.
- `SocioProphet/memory-mesh`: memory-lane health, tombstones, staleness, replay, and event-linked memory provenance.
- `SocioProphet/smart-tree`: object graph freshness, repo index health, structural churn, and package/source provenance.
- SocioSphere dashboarding: operator cards for process, policy, trust, sync, repair, and narrative events.
- DeliveryExcellence stack: estate-wide health scoring, signal-to-noise metrics, SLOs, release readiness, and regression tracking.

## First implementation target

The first implementation should produce and validate the golden examples, then expose `health snapshot`, `health explain`, `repair plan`, `events explain`, `events coalesce`, and `events verify` without destructive `repair apply`.
