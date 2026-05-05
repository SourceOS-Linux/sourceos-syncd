# SourceOS Telemetry Signal-Control Specification

Status: v0.1 design baseline
Owner surface: sourceos-syncd / PolicyFabric / AgentPlane / DeliveryExcellence / SocioSphere

## Purpose

SourceOS must not reproduce the Apple Console failure mode: strong system controls buried under undifferentiated logs, repeated expected errors, privacy redaction that destroys causality, and no operator-grade narrative.

This specification defines the SourceOS telemetry doctrine for process provenance, policy enforcement, sandbox decisions, trust checks, event coalescing, privacy-preserving disclosure, and human-readable operator summaries.

The guiding rule is:

> Controls are low-level. Telemetry is high-level. Logs are evidence, not the product.

## Lessons captured from the macOS console review

The reviewed macOS export showed useful controls but poor signal design:

- Expected sandbox denials were emitted as scary `error` records.
- Apple system daemons repeatedly inspected the same binaries and emitted duplicate messages.
- Process names, paths, targets, and responsible actors were redacted as `<private>`, preserving privacy but destroying causality.
- Security-adjacent events from `trustd`, `ecosystemanalyticsd`, `ecosystemd`, `kernel`, `cfprefsd`, `opendirectoryd`, `oahd`, `WindowServer`, and `analyticsd` were interleaved without a coherent incident object.
- Code-signing, Rosetta classification, trust evaluation, sandbox policy, iCloud metadata lookup, shell lifecycle, and UI/hardware noise were mixed into one stream.

Apple still did several things correctly:

- Internal daemons were sandboxed and denied access when they lacked entitlement.
- Trust evaluation and code-signing inspection were attempted.
- Network access for trust/static-code work was blocked by policy where appropriate.
- Privacy redaction existed by default.
- Specialized daemons performed narrow functions instead of one omnipotent process.

SourceOS should keep those controls and replace the operator experience.

## SourceOS telemetry principles

### 1. Expected control behavior is not an error

A sandbox denial is often the desired outcome. SourceOS must classify policy outcomes by semantics, not by raw syscall result.

Required outcome taxonomy:

- `allowed`: access permitted by policy.
- `blocked_expected`: access denied by policy and expected for this actor/capability profile.
- `blocked_unexpected`: access denied, not normally expected for this actor, but not attack-like.
- `blocked_attack_like`: access denied and matched suspicious behavior, exploit pattern, or privilege boundary probing.
- `degraded`: verification or enrichment could not complete, but a safe fallback was used.
- `failed`: invariant failure or user-visible failure.

### 2. One cause should produce one canonical event

Subsystem logs are evidence. The product surface is a normalized event.

A process launch should not appear as dozens of independent messages. SourceOS must generate one canonical `process.exec` event and attach evidence from subprocesses, policy engines, trust engines, package managers, and sync layers.

### 3. Redact values, not causal structure

Privacy mode must preserve forensic shape. A user may see:

> A package-managed shell binary launched from a Homebrew-like package prefix and exited cleanly.

An administrator or forensic profile may additionally see:

- executable path
- content hash
- parent PID
- launch actor
- command arguments, with secret redaction
- package receipt
- signer
- trust roots
- sandbox profile
- policy decision trace

### 4. Security telemetry and analytics telemetry must be separate

Analytics must never look like security telemetry. Compatibility classification, performance metering, product analytics, and telemetry enrichment must be opt-in or policy-gated and emitted under separate lanes.

Required lanes:

- `security`
- `policy`
- `process_lifecycle`
- `identity`
- `trust`
- `package_provenance`
- `sync`
- `developer_diagnostics`
- `hardware_ui`
- `analytics`

The default operator view should suppress `hardware_ui`, `analytics`, and raw `developer_diagnostics` unless they causally attach to a security or reliability event.

### 5. Verification must be local-first

SourceOS baseline verification must not require silent network access. Trust checks should use local manifests, local transparency logs, package provenance, reproducible-build metadata, and cached enterprise trust roots.

Network trust lookup is allowed only when policy explicitly permits it and the event records:

- destination class
- policy rule
- reason
- cache status
- result
- failure mode

### 6. Noise is a platform defect

Every daemon has a noise budget. Duplicate records must be coalesced by actor, target, decision, policy rule, and time window.

Required coalescing fields:

- `event_fingerprint`
- `first_seen`
- `last_seen`
- `count`
- `suppressed_count`
- `coalesce_window_ms`
- `sample_evidence_refs`

## Canonical event classes

### process.exec

A process or agent execution event.

Must include actor, parent, binary identity, package origin, signature state, capability profile, sandbox profile, launch reason, environment class, network posture, file posture, and exit status when available.

### policy.decision

A capability, sandbox, IPC, filesystem, network, identity, or sync authorization decision.

Must include actor, operation, target class, target redaction class, policy bundle, policy rule, decision, semantic outcome, and explanation.

### trust.evaluation

A code identity, package identity, build attestation, or certificate/trust evaluation.

Must include local/remote mode, signer, signature state, package provenance, digest, root of trust, revocation/cache posture, and degradation reason when incomplete.

### telemetry.coalesced

A synthetic event created when repeated raw records collapse into one operator-facing event.

Must include fingerprint, count, first/last seen, representative samples, and whether any repeated event changed severity.

### operator.narrative

A human-facing summary generated from canonical events and evidence.

Must include a short summary, risk readout, policy explanation, next recommended action, and drill-down links.

## Severity model

Severity is not the same as raw log level.

Required severities:

- `trace`: raw diagnostic details, disabled by default.
- `debug`: developer-only detail.
- `info`: normal lifecycle or successful state transition.
- `notice`: expected policy block or minor degraded enrichment.
- `warning`: unexpected but contained behavior.
- `error`: failed invariant, user-visible failure, or security-relevant degradation.
- `critical`: active compromise signal, data loss, privilege escalation, or control-plane failure.

Expected sandbox denials should usually be `notice`, not `error`.

## Operator narrative requirements

Every canonical event must support a concise human explanation.

Example format:

```text
19:21:58 — Package-managed shell launched and exited cleanly.
Actor: local interactive shell
Binary: package-managed arm64 shell
Trust: local signature/provenance checked; no network trust lookup performed
Policy: internal metadata reads blocked as expected by sandbox profile
Risk: low; no persistence, privilege escalation, unknown binary, or network exfiltration observed
```

## Data model requirements

All events require:

- globally unique event ID
- monotonic and wall-clock timestamps
- host identity pseudonym
- actor identity
- causal parent reference
- lane
- event class
- semantic severity
- outcome
- evidence references
- privacy tier
- retention class
- sync policy

## Privacy tiers

- `public_summary`: safe to show in public/demo logs.
- `user_private`: visible to the machine owner.
- `admin_forensic`: visible to authorized admin or incident role.
- `sealed_secret`: stored as opaque or encrypted evidence; never rendered by default.

## Implementation requirements

1. Build a canonical event envelope.
2. Build a process provenance collector.
3. Build a policy-decision normalizer.
4. Build expected-denial classification.
5. Build duplicate suppression and noise budgeting.
6. Build local-first trust/provenance attestation.
7. Build operator narrative generation.
8. Build privacy-tiered rendering.
9. Build DeliveryExcellence metrics for telemetry signal quality.
10. Build SocioSphere dashboard cards for process, policy, trust, and narrative views.

## Non-goals

SourceOS should not clone Apple Console.
SourceOS should not dump raw subsystem logs as the primary operator interface.
SourceOS should not blur analytics and security.
SourceOS should not require cloud connectivity for baseline trust.
SourceOS should not hide causal structure behind blanket redaction.

## Acceptance criteria

The first complete implementation is acceptable when a noisy process launch produces:

- one canonical process event
- one or more attached policy/trust evidence records
- coalesced duplicate denials
- a human narrative
- a privacy-preserving default view
- a forensic drill-down view
- deterministic local attestation
- no false `error` severity for expected blocks
- metrics showing raw-to-canonical event reduction ratio
