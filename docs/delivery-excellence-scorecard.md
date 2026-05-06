# Delivery Excellence Scorecard

Status: v0.1 local scorecard

`sourceos-syncd` now emits Delivery Excellence-compatible scorecards from State Integrity Reports. The local evaluator gives release, readiness, and estate-health tooling a structured way to score a component before the full Delivery Excellence ingestion service is wired in.

## Purpose

A State Integrity Report explains component health. A Delivery Excellence scorecard turns that health into an operational readiness decision.

The scorecard answers:

- Is the report contract valid?
- Is the component unsafe, degraded, watchlisted, or ready?
- Are there critical invariant failures?
- Is disk pressure acceptable?
- Is replay lag present?
- Are policy counts visible?
- Is attestation present?
- Which gates block readiness?

## Decision contract

Schema:

```text
sourceos.delivery-scorecard/v1alpha1
```

Canonical schema file:

```text
schemas/sourceos.delivery-scorecard.v1alpha1.schema.json
```

Fixture:

```text
examples/scorecards/healthy.scorecard.json
```

## CLI

Evaluate a report:

```bash
sourceos-syncd scorecard evaluate \
  --file /tmp/sourceos-syncd.snapshot.json
```

Validate a scorecard:

```bash
sourceos-syncd scorecard validate \
  --file examples/scorecards/healthy.scorecard.json
```

Wrap a scorecard as evidence:

```bash
sourceos-syncd evidence wrap \
  --file /tmp/sourceos-syncd.scorecard.json \
  --type delivery-scorecard \
  --subject sourceos-syncd
```

## Status values

- `ready`: high score and no blocking gates.
- `watch`: acceptable but with minor debt or missing attestation.
- `degraded`: significant warning/debt profile.
- `blocked`: readiness gate failed.

## Gates

The local scorecard currently evaluates:

- `contract.valid`
- `diagnosis.not_unsafe`
- `critical_invariants.none`
- `disk.not_critical`

## Score dimensions

The scorecard carries:

- diagnosis summary
- report contract errors
- invariant failures and warnings
- critical failures
- lane statuses
- replay lag
- disk pressure
- policy decision counts
- attestation state

## Stable integration loop

This closes the first SourceOS control loop:

```text
State Integrity Report
  -> PolicyFabric-compatible decisions
  -> AgentPlane-compatible trust decision
  -> Lampstand-compatible evidence envelope
  -> Delivery Excellence scorecard
```

## Replacement path for Delivery Excellence

The local evaluator should later become an ingestion source for `SocioProphet/delivery-excellence`:

1. Read State Integrity Reports from SourceOS components.
2. Validate report and scorecard schema.
3. Score gates and dimensions.
4. Preserve scorecard evidence with Lampstand.
5. Surface component readiness in dashboards and release gates.
6. Fail release readiness on blocked or unsafe state.

## Current limits

The local scorecard is deterministic but not yet a fleet dashboard. It does not yet aggregate across repos, compare historical regressions, or enforce repository branch protection. Those belong in the Delivery Excellence repos.
