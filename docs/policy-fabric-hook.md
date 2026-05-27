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
  "data_class": "internal",
  "decision_boundary": {
    "decision_scope": "policy-only",
    "runtime_effect_performed": false,
    "authority_mutation_performed": false,
    "state_repair_performed": false,
    "ledger_write_performed": false,
    "downstream_refs": [
      "SourceOS-Linux/sourceos-spec#113",
      "SourceOS-Linux/sourceos-syncd#30"
    ]
  }
}
```

## Boundary invariant

The local hook emits policy decisions only.

It does not perform:

- runtime effects;
- agent grant or authority mutation;
- state repair;
- ledger writes;
- replication;
- bridge export;
- memory writeback.

The hard chain is:

```text
state observation/report input = evidence
policy decision = local or remote policy evaluation
runtime effect = separate admission/effect decision
authority/grant mutation = separate Agent Registry / grant-state decision
state integrity report = ledger/report evidence only
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

The top-level `policy.policy_decisions` field remains numeric and dashboard-friendly. Detailed sample decisions live under `diagnosis.policy` so the State Integrity Report top-level contract remains closed. Every sample decision carries `decision_boundary` so report readers can distinguish policy evaluation from runtime action.

## Intended PolicyFabric replacement path

The local stub should later be replaced by a PolicyFabric client that preserves the same output shape:

1. Build `PolicyRequest` from lane, action, subject, object, and data class.
2. Send request to PolicyFabric.
3. Receive `sourceos.policy-decision/v1alpha1` response.
4. Confirm `decision_boundary.decision_scope = policy-only`.
5. Count statuses into `policy.policy_decisions`.
6. Attach representative explanations under `diagnosis.policy.sample`.
7. Preserve sensitive object details through redaction, not omission.

## Estate expectations

- PolicyFabric owns final policy semantics.
- SourceOS runtime-effect decisions are separate from policy decisions.
- Agent Registry / grant-state decisions are separate from policy decisions.
- AgentPlane consumes policy decisions before agent action.
- Lampstand preserves significant policy decisions as evidence.
- Delivery Excellence scores policy friction and redaction rates.
- Secure and repair lanes fail closed until explicit grants exist.

## Validation

The unit tests reject policy decisions that claim to perform runtime effects or authority mutation. This prevents the local hook from becoming a hidden execution or grant-state surface.
