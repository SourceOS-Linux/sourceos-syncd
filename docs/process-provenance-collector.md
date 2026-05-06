# SourceOS Process Provenance Collector Contract

Status: v0.1 implementation contract
Owner surface: sourceos-syncd / AgentPlane / PolicyFabric / SourceOS base

## Purpose

The process provenance collector turns low-level process activity into canonical SourceOS events. Its job is not to dump syscall logs. Its job is to answer:

- what launched;
- who or what caused it;
- what binary identity was executed;
- whether the binary came from a trusted package/source class;
- what policy and trust posture applied;
- when the process exited;
- whether the launch produced expected policy blocks, unexpected behavior, or attack-like behavior.

## Required event linkage

Every process lifecycle trace must have at least:

1. `process.exec`
2. zero or more attached `policy.decision` events
3. zero or more attached `trust.evaluation` events
4. optional `telemetry.coalesced` events for repeated low-level evidence
5. `process.exit` when exit is observed

`process.exec` is the root event unless the process was launched by another canonical event, such as `agent.action`, `sync.replication`, `object.repair`, or `policy.decision`.

## Process identity tuple

The collector must produce this minimum tuple:

- `pid`: local process identifier when available.
- `ppid`: parent process identifier when available.
- `uid_class`: `root`, `user`, `service`, `agent`, `unknown`.
- `gid_class`: `admin`, `staff`, `service`, `agent`, `unknown`.
- `executable_path_class`: `system`, `package_manager`, `user_local`, `container`, `remote_mount`, `ephemeral_tmp`, `unknown`.
- `content_hash`: `sha256:<hex>` when readable and policy allows hashing.
- `package_origin`: `system`, `package_manager`, `user_local`, `container`, `remote`, `unknown`.
- `signature_state`: `valid`, `unsigned`, `ad_hoc`, `unknown`, `invalid`, `not_applicable`.
- `parent_command_class`: `interactive_shell`, `system_service`, `agent_action`, `package_hook`, `scheduled_job`, `remote_session`, `unknown`.
- `environment_class`: `user_interactive`, `system_service`, `agent_sandbox`, `container`, `recovery`, `unknown`.
- `launch_reason`: `interactive`, `scheduled`, `service_activation`, `agent_dispatch`, `package_script`, `boot`, `repair`, `sync`, `unknown`.

## Executable identity record

The executable identity record is privacy-tiered. The default operator view must preserve causality without exposing raw secrets.

Required fields:

- `path_class`
- `display_path`
- `exact_path_ref` when authorized
- `content_hash`
- `package_origin`
- `package_receipt_ref`
- `signature_state`
- `signer_display`
- `trust_mode`
- `network_lookup`

## Parent/root trace assignment

The collector must assign stable trace fields:

- `trace_id`: stable for the process lifecycle and attached events.
- `root_event_id`: the root canonical event for the chain.
- `parent_event_id`: direct cause when known.
- `span_id`: unique event-local span.

If parent process identity is known but no parent canonical event exists, the process event still records parent metadata as evidence. It must not invent a parent event.

## Package-origin detection hook

The collector should classify package origin through ordered checks:

1. SourceOS package receipt or BootReleaseSet manifest.
2. OS/vendor system manifest.
3. package-manager database or receipt.
4. container image manifest.
5. signed agent/runtime manifest.
6. user-local path class.
7. unknown.

Failure to classify origin is `degraded` only when policy requires classification. Otherwise it is `unknown` with low severity.

## Exit linkage

When process exit is observed, emit `process.exit` with the same `trace_id` and `root_event_id` as the corresponding `process.exec`.

Required exit fields should be carried as evidence or subject display until a richer exit-specific schema exists:

- `pid`
- `exit_code` or signal
- `runtime_ms` when available
- `resource_summary_ref` when available
- `termination_reason` when known

## Privacy requirements

Default user view:

- preserve actor, subject, path class, package origin, signer state, risk, and next action;
- redact exact path and command arguments by default;
- do not redact so aggressively that causality is lost.

Admin forensic view:

- may reveal exact executable path, command args with secret masking, parent pid, content hash, package receipt, signer, sandbox profile, and evidence references.

## Expected examples

### Clean package-managed shell launch

- `event_class=process.exec`
- `lane=process_lifecycle`
- `severity=info`
- `outcome=allowed`
- `trust.mode=local_first`
- `trust.package_origin=package_manager`
- `trust.network_lookup=not_attempted`

### Expected telemetry sandbox block attached to shell launch

- `event_class=policy.decision`
- `lane=policy`
- `severity=notice`
- `outcome=blocked_expected`
- `decision.explanation_code=POLICY_EXPECTED_METADATA_BOUNDARY`

### Process exit

- `event_class=process.exit`
- `lane=process_lifecycle`
- `severity=info`
- `outcome=allowed`
- same `trace_id` and `root_event_id` as `process.exec`

## Non-goals

The collector must not become a raw syscall recorder.
The collector must not expose secrets by default.
The collector must not treat every unsigned script as malicious.
The collector must not require network access for baseline trust.
The collector must not emit a new operator event for every duplicate low-level denial.

## Acceptance criteria

- A shell launch produces one canonical `process.exec` event.
- Process exit attaches to the same trace.
- Package-managed binaries are distinguishable from user-local and unknown binaries.
- Default rendering does not require exact private paths.
- Expected policy blocks are attached or coalesced instead of emitted as false errors.
