# PolicyFabric Hook

Status: v0.1 local stub

`sourceos-syncd` now includes a PolicyFabric-compatible local policy hook. The real PolicyFabric service remains the target authority, but the local hook gives State Integrity Reports a stable decision shape today.

## Purpose

The hook lets reports answer four questions before full cross-repo integration exists:

1. Which policy engine evaluated the state?
2. Which lane/action pairs were allowed, denied, redacted, or deferred?
3. Which explanation code should operators and agents see?
4. How many decisions of each class should Delivery Excellence score?

## Decision contract

Schema:

```text
sourceos.policy-decision/v1alpha1
```

Canonical schema file:

```text
schemas/sourceos.policy-decision.v1alpha1.schema.json
```

Decision fields:

```json
{
  "schema": "sourceos.policy-decision/v1alpha1",
  "decision_id": "policy-example",
  "generated_at": "2026-05-05T00:00:00Z",
  "engine": "policy-fabric-local-stub",
  "action": "agent_access",
  "lane": "secure",
  "status": "denied",
  "reason": "secure_lane_requires_explicit_grant",
  "subject": "sourceos-syncd",
  "object_id": null,
  "data_class": "internal"
}
```

## Local default behavior

The local stub is conservative:

- `secure` + `agent_access` -> `denied`
- `secure` + `replicate` -> `denied`
- `secure` + `index` -> `redacted`
- `repair` + `agent_access` -> `denied`
- `repair` + `write` -> `denied`
- `ephemeral` + `retain` -> `deferred`
- `secret` or `credential` data with `replicate` or `agent_access` -> `denied`
- unknown actions -> `deferred`
- ordinary lane/action pairs -> `allowed`

## Report integration

Store-backed reports now include local policy evaluation output:

```json
{
  "policy": {
    "policy_engine": "policy-fabric-local-stub",
    "policy_version": "v0.1.0-local-stub",
    "policy_decisions": {
      "allowed": 31,
      "deferred": 1,
      "denied": 6,
      "redacted": 2
    }
  },
  "diagnosis": {
    "policy": {
      "engine": "policy-fabric-local-stub",
      "counts": {},
      "sample": []
    }
  }
}
```

The top-level `policy.policy_decisions` field remains numeric and dashboard-friendly. Detailed sample decisions live under `diagnosis.policy` so the State Integrity Report top-level contract remains closed.

## Intended PolicyFabric replacement path

The local stub should later be replaced by a PolicyFabric client that preserves the same output shape:

1. Build `PolicyRequest` from lane, action, subject, object, and data class.
2. Send request to PolicyFabric.
3. Receive `sourceos.policy-decision/v1alpha1` response.
4. Count statuses into `policy.policy_decisions`.
5. Attach representative explanations under `diagnosis.policy.sample`.
6. Preserve sensitive object details through redaction, not omission.

## Estate expectations

- PolicyFabric owns final policy semantics.
- AgentPlane consumes policy decisions before agent action.
- Lampstand preserves significant policy decisions as evidence.
- Delivery Excellence scores policy friction and redaction rates.
- Secure and repair lanes fail closed until explicit grants exist.
