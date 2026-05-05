# Security

`sourceos-syncd` is a local-first state integrity daemon substrate. It is expected to become sensitive infrastructure because it may eventually manage object state, actor state, schema migration, repair, provenance, policy-governed replication, and local-first sync.

## Current posture

The current trust surface is conservative:

- no declared background service yet;
- no declared network listener yet;
- no declared replication egress yet;
- no declared credential store yet;
- no declared containers yet;
- no shell/tool execution by default;
- no browser or terminal control;
- no model-provider credentials.

Any implementation that changes this posture must update `TRUST_SURFACE.yaml` in the same pull request.

## Blocking rule

Block changes that introduce any of the following without a trust-surface update:

- LaunchAgent, LaunchDaemon, systemd unit, scheduled task, cron job, or daemon installer;
- listener, socket, WebSocket, gRPC, HTTP, MCP, ACP, or replication transport;
- credential, token, keychain, SecretRef, OAuth, SSH-agent, or API-key handling;
- repair actions that mutate state without policy admission and replay evidence;
- schema migrations without rollback and provenance notes;
- local path, actor, device, object, or provenance metadata in logs without redaction;
- container, VM, Podman, Docker, or local Kubernetes runtime;
- purge/prove-clean regression.

## Cleanup and revocation

Before shipping an installable daemon, this repo must provide:

```text
scripts/doctor
scripts/network-surface
scripts/credential-surface
scripts/policy-surface
scripts/purge
scripts/prove-clean
```

The minimum proof of cleanup is: no process, no launch item, no listener, no credential, no service token drift, and no retained local state unless explicitly requested by the user.
