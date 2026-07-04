# SourceOS Policy Decision Normalizer

Status: v0.1 implementation contract
Owner surface: sourceos-syncd / PolicyFabric / AgentPlane / SocioSphere

## Purpose

The policy decision normalizer converts raw policy, sandbox, IPC, filesystem, network, identity, and sync authorization observations into canonical `policy.decision` events.

Its primary job is to prevent secure expected behavior from becoming operator-facing garbage. A denied operation is not automatically an error. It must be classified by policy intent, actor profile, target class, and security semantics.

## Input classes

The normalizer accepts observations from:

- kernel sandbox or capability decisions;
- PolicyFabric authorization decisions;
- local IPC/mach/dbus/service lookup gates;
- filesystem read/write/metadata gates;
- network egress, trust lookup, and endpoint gates;
- identity, entitlement, DID, credential, and role gates;
- sync, replication, retention, purge, and repair gates;
- agent runtime admission and action gates.

## Canonical output

Every normalized policy observation emits or attaches a canonical `policy.decision` event with:

- `decision.policy_bundle`
- `decision.policy_rule`
- `decision.operation`
- `decision.target_class`
- `decision.result`
- `decision.semantic_outcome`
- `decision.explanation_code`
- `severity`
- `outcome`
- `operator_narrative`

## Result vs semantic outcome

`decision.result` records the mechanical policy decision:

- `allow`
- `deny`
- `defer`
- `degrade`

`decision.semantic_outcome` records SourceOS interpretation:

- `allowed`
- `blocked_expected`
- `blocked_unexpected`
- `blocked_attack_like`
- `degraded`
- `failed`
- `observed`

The two must not be conflated.

Examples:

- `result=deny`, `semantic_outcome=blocked_expected`: sandbox blocked a telemetry component from reading raw executable data outside its profile.
- `result=deny`, `semantic_outcome=blocked_attack_like`: a user process probed privileged identity, kernel, or agent control-plane boundaries.
- `result=degrade`, `semantic_outcome=degraded`: trust lookup could not complete, but local-first fallback preserved safety.
- `result=allow`, `semantic_outcome=allowed`: policy permitted an expected action.

## Severity mapping

The normalizer must assign severity from semantic outcome and registry defaults, not raw denial status.

Default mapping:

- `allowed` -> `info`
- `blocked_expected` -> `notice`
- `blocked_unexpected` -> `warning`
- `blocked_attack_like` -> `critical`
- `degraded` -> `warning`
- `failed` -> `error`
- `observed` -> `info`

Registry entries may narrow severity but must not inflate expected blocks to `error` unless the policy rule explicitly says the block indicates user-visible failure or integrity loss.

## Explanation-code registry

Every `policy.decision` must reference a known explanation code.

Minimum required codes:

- `POLICY_EXPECTED_METADATA_BOUNDARY`
- `POLICY_EXPECTED_NETWORK_DISABLED`
- `POLICY_UNEXPECTED_FILE_READ`
- `POLICY_ATTACK_LIKE_PRIVILEGE_BOUNDARY_PROBE`
- `POLICY_DEGRADED_TRUST_LOCAL_ONLY`

The registry records:

- code
- title
- domain
- result
- semantic outcome
- severity
- risk
- default summary
- default why
- default next action
- allowed operation classes
- allowed target classes

## Normalization rules

1. Look up `explanation_code` in the registry.
2. Validate that the observed result matches registry result unless an override is explicitly allowed.
3. Validate that operation class and target class match the registry entry.
4. Set event `outcome` from registry semantic outcome unless caller provides a stricter compatible outcome.
5. Set event `severity` from registry severity unless caller provides a stricter compatible severity.
6. Fill operator narrative from registry defaults when caller does not provide specific narrative text.
7. Preserve raw evidence as evidence references, not primary product surface.
8. Attach to an existing root trace when parent/root IDs are provided.

## Compatibility rules

A caller may provide more specific summary/why/next-action text, but may not use a known explanation code with contradictory semantics.

Invalid examples:

- `POLICY_EXPECTED_METADATA_BOUNDARY` with `outcome=blocked_attack_like`.
- `POLICY_ATTACK_LIKE_PRIVILEGE_BOUNDARY_PROBE` with `severity=notice`.
- `POLICY_EXPECTED_NETWORK_DISABLED` with `result=allow`.

## Non-goals

The normalizer is not a replacement for the policy engine.
It does not decide access by itself.
It records and explains policy decisions already made by the responsible control surface.
It must not hide attack-like events under benign explanation codes.
It must not generate false errors for expected blocks.

## Acceptance criteria

- Known explanation codes validate against registry semantics.
- Expected sandbox/capability denials render as `notice` + `blocked_expected`.
- Network-disabled policy outcomes render as successful local-first safety, not failure.
- Unexpected file reads render as `warning` unless explicitly attack-like.
- Privilege-boundary probes render as `critical` + `blocked_attack_like`.
- Generated policy events validate against the canonical event schema.
- Invalid contradictory combinations fail validation.
