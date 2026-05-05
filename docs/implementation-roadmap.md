# SourceOS Telemetry Signal-Control Implementation Roadmap

Status: v0.1 execution baseline

This roadmap turns the telemetry-noise-control specification into implementation work across `sourceos-syncd` and adjacent estate surfaces.

## Completion definition

This work is complete when SourceOS can ingest noisy low-level process, policy, trust, package, and sync evidence and render one privacy-preserving, causally accurate operator event with drill-down evidence.

A complete baseline must demonstrate:

- canonical event envelope support
- process provenance capture
- policy decision normalization
- expected-denial classification
- duplicate suppression and noise budgets
- local-first trust/provenance attestation
- operator narrative generation
- privacy-tiered rendering
- DeliveryExcellence metrics for signal quality
- SocioSphere-ready dashboard contract

## Phase 0 — Specification capture

Status: in progress

Deliverables:

- `docs/telemetry-noise-control-spec.md`
- `docs/canonical-event-envelope.md`
- `docs/implementation-roadmap.md`
- issue backlog
- README integration

Acceptance criteria:

- the doctrine is explicit
- controlled vocabularies exist
- one process-launch example exists
- expected sandbox denials are classified below error severity

## Phase 1 — Event schema package

Target: sourceos-syncd

Deliverables:

- JSON Schema for `sourceos.event.v0.1`
- Rust/Go/TypeScript-compatible schema naming rules, depending on implementation language selected
- controlled-vocabulary validation
- sample events for process, policy, trust, and coalesced telemetry
- schema test fixtures

Acceptance criteria:

- invalid severity/outcome/lane/event-class values fail validation
- required causality fields are enforced
- privacy tier is required
- network trust posture is explicit

## Phase 2 — Process provenance collector

Target: sourceos-syncd / AgentPlane

Deliverables:

- process identity tuple
- parent/root trace assignment
- executable identity record
- package-origin detection hook
- exit status capture
- launch-reason field

Minimum identity tuple:

- pid
- ppid
- uid/gid class
- executable path class
- content hash
- package origin
- signer state
- parent command class
- environment class

Acceptance criteria:

- a shell launch produces one `process.exec` event
- process exit attaches to the same trace
- package-managed binaries are distinguished from user-local and unknown binaries

## Phase 3 — Policy decision normalizer

Target: sourceos-syncd / PolicyFabric

Deliverables:

- policy decision event contract
- semantic outcome mapping
- explanation-code registry
- default expected-denial rules
- file, IPC, network, identity, sync operation classes

Required explanation-code examples:

- `POLICY_EXPECTED_METADATA_BOUNDARY`
- `POLICY_EXPECTED_NETWORK_DISABLED`
- `POLICY_UNEXPECTED_FILE_READ`
- `POLICY_ATTACK_LIKE_PRIVILEGE_BOUNDARY_PROBE`
- `POLICY_DEGRADED_TRUST_LOCAL_ONLY`

Acceptance criteria:

- expected sandbox denies render as `notice` + `blocked_expected`
- unexpected denials render as `warning` unless attack-like
- policy result and semantic outcome are both preserved

## Phase 4 — Trust and package provenance

Target: sourceos-syncd / package tooling / SourceOS base

Deliverables:

- local-first trust evaluation event
- package receipt lookup abstraction
- content hash capture
- signature state capture
- network lookup state field
- degraded verification handling

Acceptance criteria:

- unsigned scripts are not automatically treated as malicious
- package-managed binaries can be locally verified
- trust checks never silently use network access
- degraded trust is explainable

## Phase 5 — Noise budget and coalescing engine

Target: sourceos-syncd / DeliveryExcellence

Deliverables:

- event fingerprint algorithm
- duplicate suppression window
- per-daemon noise budget
- raw-to-canonical event ratio metric
- suppressed event sample references
- severity escalation if repeated events change risk class

Acceptance criteria:

- repeated identical denials collapse into one event
- coalesced event preserves count and evidence samples
- severity is not inflated by duplication alone
- high-volume noisy components can be measured and fixed

## Phase 6 — Operator narrative generator

Target: sourceos-syncd / SocioSphere

Deliverables:

- narrative template registry
- risk readout
- next-action recommendation
- privacy-tier-aware rendering
- forensic drill-down references

Acceptance criteria:

- a noisy shell launch renders as a concise narrative
- private paths are not required for default comprehension
- admin forensic view can reveal exact path/hash/provenance when authorized

## Phase 7 — Dashboard and estate integration

Targets:

- SocioSphere for dashboarding
- PolicyFabric for policy explanation
- AgentPlane for agent/process lineage
- DeliveryExcellence for metrics

Deliverables:

- dashboard card contract
- policy explanation API contract
- agent lineage integration contract
- signal-quality metrics export

Acceptance criteria:

- operator sees one card per causal event
- drill-down exposes evidence without raw-log dumping by default
- metrics show event reduction and false-error suppression

## Turn estimate

From the current state, a solid working baseline should take about 8 focused turns.

Turn 1: capture spec, schema seed, roadmap, backlog, README.
Turn 2: add JSON Schema and sample event fixtures.
Turn 3: add minimal process provenance collector contract/stub.
Turn 4: add policy-decision normalizer and explanation-code registry.
Turn 5: add trust/package provenance contract and local-first posture model.
Turn 6: add coalescing/noise-budget engine design and tests.
Turn 7: add operator narrative contract and sample renderer.
Turn 8: wire README, issues, and cross-repo integration notes for SocioSphere, PolicyFabric, AgentPlane, and DeliveryExcellence.

A production-grade daemon will take additional engineering beyond this baseline, but 8 turns should get us to a coherent, reviewable, implementation-ready foundation.
