# sourceos-syncd

SourceOS State Integrity daemon: local-first object, actor, schema, repair, provenance, and policy-governed replication substrate.

## Mission

`sourceos-syncd` is the reference substrate for SourceOS local-first state integrity. It should make state observable, explainable, policy-governed, repairable, attestable, and safe for agent use.

This repository is the canonical home for the SourceOS State Integrity Report, Index Lane model, telemetry signal-control doctrine, and the first SourceOS control-plane contract spine.

## Core concepts

- **State Integrity Report**: durable JSON health artifact for stateful daemons, indexes, sync engines, memory stores, and repair systems.
- **Index Lanes**: explicit operational classes for normal, priority, secure, ephemeral, memory, policy, audit, tombstone, migration, repair, and archive state.
- **Diagnosis layer**: interpreted health beside raw telemetry.
- **Repair plan**: non-destructive preview before any state mutation or purge.
- **Policy-native indexing**: PolicyFabric controls indexing, retention, replication, purge, and agent access.
- **Attested operations**: Lampstand preserves important state reports and repair actions as signed evidence.
- **Telemetry signal control**: raw logs are evidence, not the product; expected policy blocks are classified correctly and duplicate noise is coalesced.
- **Operator narrative**: SourceOS explains what happened, why policy acted, what risk remains, and what action is required.
- **Control-plane receipts**: events, services, capabilities, launch manifests, and incident bundles share one typed vocabulary.

## Specs

- [`docs/specs/sourceos-state-integrity-report.md`](docs/specs/sourceos-state-integrity-report.md)
- [`docs/specs/sourceos-index-lanes.md`](docs/specs/sourceos-index-lanes.md)
- [`docs/specs/sourceos-control-plane-integration.md`](docs/specs/sourceos-control-plane-integration.md)
- [`docs/telemetry-noise-control-spec.md`](docs/telemetry-noise-control-spec.md)
- [`docs/canonical-event-envelope.md`](docs/canonical-event-envelope.md)
- [`docs/implementation-roadmap.md`](docs/implementation-roadmap.md)
- [`adr/0001-sourceos-control-plane.md`](adr/0001-sourceos-control-plane.md)

## JSON Schemas

State integrity:

- [`schemas/sourceos.state-integrity-report.v1alpha1.schema.json`](schemas/sourceos.state-integrity-report.v1alpha1.schema.json)
- [`schemas/sourceos.repair-plan.v1alpha1.schema.json`](schemas/sourceos.repair-plan.v1alpha1.schema.json)

Control plane:

- [`schemas/sourceos-event.schema.json`](schemas/sourceos-event.schema.json)
- [`schemas/sourceos-service.schema.json`](schemas/sourceos-service.schema.json)
- [`schemas/sourceos-capability.schema.json`](schemas/sourceos-capability.schema.json)
- [`schemas/sourceos-launch-manifest.schema.json`](schemas/sourceos-launch-manifest.schema.json)
- [`schemas/sourceos-incident.schema.json`](schemas/sourceos-incident.schema.json)

The runtime validator is standard-library-only today; the schemas are the canonical external contract for downstream validators, SDKs, dashboards, and cross-repo integrations.

## Golden examples

Health and repair:

- [`examples/health/healthy.snapshot.json`](examples/health/healthy.snapshot.json)
- [`examples/health/degraded.snapshot.json`](examples/health/degraded.snapshot.json)
- [`examples/health/repair-plan.json`](examples/health/repair-plan.json)

Control plane:

- [`examples/events/apple-mdm-entitlement-denial.coalesced.json`](examples/events/apple-mdm-entitlement-denial.coalesced.json)
- [`examples/events/apple-darkwake-network-receipt.json`](examples/events/apple-darkwake-network-receipt.json)
- [`examples/services/bearbrowser.service.json`](examples/services/bearbrowser.service.json)
- [`examples/capabilities/browser-gpu-spawn.capability.json`](examples/capabilities/browser-gpu-spawn.capability.json)
- [`examples/launch/bearbrowser.launch-manifest.json`](examples/launch/bearbrowser.launch-manifest.json)
- [`examples/incidents/bearbrowser-identity-leak.incident.json`](examples/incidents/bearbrowser-identity-leak.incident.json)

## Validation

Bootstrap control-plane validation uses only Python standard-library checks:

```bash
python3 tools/validate_control_plane_examples.py
```

This validator is intentionally narrower than a full JSON Schema validator. It enforces schema-version alignment, controlled vocabulary basics, required operator narrative fields, causality fields, service capability lists, and the invariant that expected policy blocks do not render as warning/error by default.

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
sourceos control-plane validate
sourceos services graph
sourceos incidents explain
```

## Intended local HTTP contract

Local-only by default:

- `/healthz` liveness
- `/readyz` readiness
- `/statez` structured State Integrity Report
- `/events` canonical event stream, privacy-tiered by caller capability
- `/events/{id}` canonical event with evidence references
- `/events/{id}/explain` human operator narrative
- `/services` local service graph
- `/services/{id}` service manifest and health state
- `/capabilities` capability registry
- `/incidents` local incident bundle index
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
- Wake, launch, identity, parser, incident, and telemetry activity must produce receipts instead of opaque logs.

## Control-plane release gates

A SourceOS service or product is not release-ready unless:

1. It has a service manifest.
2. It emits canonical events or explicitly documents why it does not.
3. It declares required, optional, and denied capabilities.
4. It has a hermetic launch manifest if it is an app.
5. It produces an incident bundle for crashes, denial storms, wake anomalies, identity mismatches, and parser faults.
6. It does not perform silent remote trust lookup.
7. It does not emit remote telemetry by default.
8. It coalesces repeated expected denials.
9. It preserves privacy while retaining causal structure.
10. It has a DeliveryExcellence signal-quality metric.

## Estate integration targets

- `SocioProphet/policy-fabric`: policy decisions for indexing, retention, replication, purge, agent access, telemetry outcomes, explanation codes, capability grants, and release gates.
- `SocioProphet/agentplane`: trust gates before agent actions against state substrates and process/agent lineage traces.
- `SocioProphet/lampstand`: signed evidence, repair records, event attestations, and incident timelines.
- `SocioProphet/memory-mesh`: memory-lane health, tombstones, staleness, replay, and event-linked memory provenance.
- `SocioProphet/smart-tree`: object graph freshness, repo index health, structural churn, and package/source provenance.
- SourceOS browser surfaces: product identity invariants, helper topology, hermetic app launch, parser/media worker receipts, and local incident bundles.
- TurtleTerm / developer runtime: developer-mode scope, tty/session provenance, command-hash ledger, privileged-action receipts, and toolchain environment manifests.
- SocioSphere dashboarding: operator cards for process, policy, trust, sync, repair, incident, wake, identity, and narrative events.
- DeliveryExcellence stack: estate-wide health scoring, signal-to-noise metrics, SLOs, release readiness, and regression tracking.

## First implementation target

The first implementation should produce and validate the golden examples, then expose `health snapshot`, `health explain`, `repair plan`, `events explain`, `events coalesce`, and `events verify` without destructive `repair apply`.

The control-plane extension adds one immediate next target: turn `tools/validate_control_plane_examples.py` into a CI gate, then replace the bootstrap checks with full JSON Schema validation once a dependency policy is selected.
