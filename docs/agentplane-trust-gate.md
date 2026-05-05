# AgentPlane Trust Gate

Status: v0.1 local gate

`sourceos-syncd` now emits AgentPlane-compatible trust decisions from State Integrity Reports. The local gate gives agents a deterministic way to decide whether a state substrate is safe to use before reading, writing, traversing memory, or acting against a lane.

## Purpose

Agents should not treat every local substrate as trustworthy. Before action, an agent should know:

- whether the State Integrity Report contract is valid;
- whether the requested lane exists;
- whether the report diagnosis is healthy, degraded, unsafe, stale, or unknown;
- whether degraded mode was explicitly allowed;
- whether signed evidence is required and present;
- whether policy counts indicate restricted state.

## Decision contract

Schema:

```text
sourceos.agent-trust-decision/v1alpha1
```

Canonical schema file:

```text
schemas/sourceos.agent-trust-decision.v1alpha1.schema.json
```

Decision shape:

```json
{
  "schema": "sourceos.agent-trust-decision/v1alpha1",
  "decision_id": "trust-example",
  "generated_at": "2026-05-05T00:00:00Z",
  "engine": "agentplane-local-trust-gate",
  "subject": "agentplane",
  "action": "read",
  "lane": "normal",
  "status": "allowed",
  "reason": "state_integrity_allows_agent_action",
  "report_digest": "sha256:...",
  "report_status": "healthy",
  "allow_degraded": false,
  "require_attestation": false,
  "evidence": {}
}
```

## Status values

- `allowed`: report is healthy enough for the requested lane/action.
- `degraded_allowed`: report is degraded, but the caller explicitly allowed degraded mode.
- `blocked`: lane/action should not proceed.
- `unknown`: reserved for future remote AgentPlane states.

## CLI

Evaluate a report:

```bash
sourceos-syncd trust evaluate \
  --file /tmp/sourceos-syncd.snapshot.json \
  --subject agentplane \
  --action read \
  --lane normal
```

Allow degraded mode explicitly:

```bash
sourceos-syncd trust evaluate \
  --file /tmp/sourceos-syncd.snapshot.json \
  --subject agentplane \
  --action read \
  --lane normal \
  --allow-degraded
```

Require signed attestation:

```bash
sourceos-syncd trust evaluate \
  --file /tmp/sourceos-syncd.snapshot.json \
  --subject agentplane \
  --action read \
  --lane normal \
  --require-attestation
```

Validate a decision artifact:

```bash
sourceos-syncd trust validate \
  --file examples/trust/normal-read.allowed.json
```

## Local gate rules

The local gate blocks when:

- the report contract is invalid;
- the requested lane is absent;
- signed attestation is required but missing;
- the report status is unsafe, stale, or unknown;
- the report is degraded and degraded mode was not explicitly allowed;
- the requested lane is secure or repair and policy counts indicate restrictions.

The local gate allows when:

- the report contract is valid;
- the requested lane exists;
- the report is healthy;
- attestation requirements are satisfied;
- policy counts do not indicate lane restriction.

## Evidence relationship

A trust decision is itself an evidence candidate. It can be wrapped with:

```bash
sourceos-syncd evidence wrap \
  --file /tmp/trust-decision.json \
  --type agent-trust-decision \
  --subject agentplane
```

This gives AgentPlane and Delivery Excellence a chain:

```text
State Integrity Report -> Agent Trust Decision -> Lampstand Evidence Envelope
```

## Replacement path for AgentPlane

The local gate should later become an AgentPlane consumer contract:

1. AgentPlane asks for trust evaluation before acting.
2. SourceOS provides a State Integrity Report digest and diagnosis.
3. PolicyFabric provides lane/action authorization.
4. Lampstand provides evidence and attestation state.
5. AgentPlane records which report and decision it relied on.

## Current limits

The local gate is not yet a distributed authorization system. It does not yet perform remote identity checks, capability credential validation, or signed evidence lookup. Those belong in AgentPlane, PolicyFabric, and Lampstand integration work.
