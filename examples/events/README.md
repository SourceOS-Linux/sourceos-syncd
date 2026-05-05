# Canonical Event Fixtures

These fixtures exercise `schemas/sourceos.event.v0.1.schema.json`.

## Valid fixtures

- `process-exec.package-shell.json`: package-managed shell launch with local-first trust evidence.
- `policy-decision.expected-metadata-boundary.json`: expected sandbox/capability block rendered as `notice` + `blocked_expected`.
- `trust-evaluation.local-first.json`: local-first trust verification without silent network lookup.
- `telemetry-coalesced.expected-denials.json`: repeated expected denials collapsed into one canonical event.

## Invalid fixtures

- `invalid/bad-severity.json`: uses `severity=scary`, which is not a controlled vocabulary value.
- `invalid/policy-decision-missing-decision.json`: declares `event_class=policy.decision` without the required `decision` object.

## Intended validation contract

A test runner should validate every file in this directory except `invalid/**` as passing, then validate every file in `invalid/**` as failing.

Suggested command once validation tooling is added:

```bash
sourceos-syncd events verify --schema schemas/sourceos.event.v0.1.schema.json examples/events/*.json
sourceos-syncd events verify --schema schemas/sourceos.event.v0.1.schema.json --expect-fail examples/events/invalid/*.json
```

## Doctrine coverage

These fixtures encode the initial SourceOS response to noisy system telemetry:

- raw logs are evidence, not the operator product;
- expected policy blocks are not false `error` events;
- privacy redaction preserves causal structure;
- local-first trust is explicit;
- repeated low-value events are coalesced without inflating severity.
