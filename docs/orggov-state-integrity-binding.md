# OrgGov State Integrity Binding v0.1

## Purpose

OrgGov State Integrity Binding v0.1 makes `sourceos-syncd` the local-first state integrity lane for Organization Governance Control Plane v0.

The binding connects governed work orders to SourceOS state reports, index lanes, policy decisions, canonical events, repair-plan posture, evidence references, and operator narrative.

The shared OrgGov loop is:

```text
Objective → Workroom → Actor → Role → Policy → Asset → Action → Evidence → Review → Outcome → Score → Learning
```

`sourceos-syncd` owns the local-first state, index-lane, event, repair-plan, and operator-narrative evidence portion of that loop. It does not own policy authority, product UX, agent execution, or scorecard semantics.

## Contract files

- `schemas/orggov-state-integrity-binding.v0.1.schema.json`
- `examples/orggov/state-integrity-binding.v0.1.example.json`
- `tools/validate_orggov_state_integrity_binding.py`

## Invariants

- Every binding references a workroom, work order, actor, and session.
- Every binding references a state integrity report and at least one index lane.
- Every binding includes canonical event refs and evidence refs.
- Repair posture is explicit even when no destructive repair is required.
- Operator narrative must include summary, why, next action, and remaining risk.
- Public fixtures must set `provenance.nonSecret` to true.

## Cross-repo links

- Parent: `SocioProphet/prophet-platform#406`
- SourceOS workstream: `SourceOS-Linux/sourceos-syncd#13`
- AgentPlane evidence: `SocioProphet/agentplane#104`
- Policy gate: `SocioProphet/policy-fabric#57`
- Sherlock indexing: `SocioProphet/sherlock-search#36`
- Delivery scorecard: `SocioProphet/delivery-excellence#14`

## Runtime promotion path

The v0 fixture is not yet live runtime emission. The next promotion step is to have `sourceos-syncd` emit a matching binding from a real state integrity report, with Lampstand-attestable evidence and privacy-tiered event access.
