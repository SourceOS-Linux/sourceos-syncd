# Controller Sovereignty Implementation Backlog

This backlog converts the controller-sovereignty doctrine into implementable SourceOS work.

## P0 — Contract hardening

### CS-P0-001: Event envelope fixture

Create canonical JSON fixtures for the event envelope.

Acceptance:

- Contains one valid fixture for each required event type.
- Fixtures contain no private local data.
- Fixtures are schema-checkable.

### CS-P0-002: Controller registry fixture

Create sample controller registry entries for:

- metadata indexer
- media analyzer
- filesystem maintainer
- wireless policy controller
- application updater
- network policy extension

Acceptance:

- Each fixture declares owner, capabilities, budgets, allowed states, and observability fields.
- Fixtures are redacted and synthetic.

### CS-P0-003: Case-file exemplar

Create a synthetic case-file exemplar showing a budget-exceeded metadata controller.

Acceptance:

- No real hostnames, device identifiers, user paths, or diagnostic records.
- Includes user-control gap and SourceOS design requirement.

## P1 — Parser to event mapper

### CS-P1-001: Map resource summary rows to controller events

Extend the summary parser so each row can be converted into a candidate SourceOS event.

Acceptance:

- Disk-write rows map to `ControllerBudgetObserved` or `ControllerBudgetExceeded`.
- CPU rows map to `ControllerBudgetObserved` or `ControllerBudgetExceeded`.
- Unknown controller rows map to `Unclassified` with explicit confidence.
- Raw private evidence is not emitted by default.

### CS-P1-002: Add confidence and classification fields

Add confidence fields to parsed records.

Acceptance:

- controller confidence
- stack-family confidence
- evidence confidence
- privacy redaction level

### CS-P1-003: Add synthetic unit fixtures

Add local synthetic report snippets for parser tests.

Acceptance:

- No private logs.
- Includes representative Spotlight, Photos, APFS, Wireless, and updater cases.

## P2 — Controller registry integration

### CS-P2-001: Registry loader

Build a loader for controller registry YAML documents.

Acceptance:

- Validates required fields.
- Reports missing budgets and undeclared capabilities.
- Produces normalized controller records.

### CS-P2-002: Capability diff

Compare observed event capabilities against declared controller capabilities.

Acceptance:

- Emits an advisory when a controller uses an undeclared capability.
- Emits an advisory when a controller acts outside allowed states.

### CS-P2-003: Budget evaluator

Evaluate event streams against declared budgets.

Acceptance:

- Supports CPU, disk-write, memory, and network budget classes.
- Produces budget state: within_budget, near_limit, exceeded, unknown.

## P3 — Dashboard prototype

### CS-P3-001: Terminal dashboard

Build a terminal-first sovereignty dashboard.

Acceptance:

- Groups events by controller class.
- Shows current policy profile.
- Shows last event, budget state, and recommended action.

### CS-P3-002: Profile simulation

Simulate Workstation, Investigation, Personal, and Maintenance profiles against an event stream.

Acceptance:

- Shows which events would be allowed, blocked, budgeted, or escalated.
- Produces a human-readable explanation.

## P4 — SourceOS runtime bridge

### CS-P4-001: SourceOS State Integrity Report extension

Extend the State Integrity Report model to include controller-sovereignty summaries.

Acceptance:

- Report includes controller counts, budget state, recent violations, and active profile.
- Report remains local-first and suitable for signed evidence.

### CS-P4-002: PolicyFabric bridge

Define how PolicyFabric consumes controller events and profiles.

Acceptance:

- Specifies policy inputs and outputs.
- Distinguishes observation, advisory, budget enforcement, and operator approval.

### CS-P4-003: Lampstand evidence bridge

Define which controller events should become signed evidence.

Acceptance:

- Budget exceeded events are eligible.
- Profile transitions are eligible.
- Raw private artifacts are not stored by default.

## Done criteria

The controller-sovereignty lane is minimally complete when SourceOS can:

1. Register controllers.
2. Declare capabilities and budgets.
3. Summarize local events without private payloads.
4. Evaluate budget state.
5. Explain user-control gaps.
6. Emit a State Integrity Report section for controller sovereignty.
