# Canonical Event Envelope

Status: v0.1 schema seed

This document defines the initial canonical event shape for SourceOS state integrity, telemetry normalization, policy decisions, and operator narratives.

## Envelope

```json
{
  "schema_version": "sourceos.event.v0.1",
  "event_id": "evt_...",
  "event_class": "process.exec",
  "lane": "process_lifecycle",
  "severity": "notice",
  "outcome": "blocked_expected",
  "created_at": "2026-05-04T19:21:58.369000-04:00",
  "observed_at_monotonic_ns": 0,
  "host": {
    "host_id": "host_pseudonym",
    "platform": "sourceos",
    "kernel": "...",
    "privacy_zone": "user_private"
  },
  "actor": {
    "actor_id": "actor_...",
    "actor_type": "process|agent|user|service|kernel|policy_engine",
    "display_name": "package-managed shell",
    "uid": "redacted-or-id",
    "session_id": "session_..."
  },
  "causality": {
    "parent_event_id": "evt_...",
    "root_event_id": "evt_...",
    "span_id": "span_...",
    "trace_id": "trace_..."
  },
  "subject": {
    "type": "process|file|socket|ipc_service|object|schema|replica|policy",
    "id": "subject_...",
    "display": "redacted causal label"
  },
  "decision": {
    "decision_id": "dec_...",
    "policy_bundle": "sourceos.baseline",
    "policy_rule": "telemetry-agent.filesystem.executable-metadata-only",
    "operation": "file-read-data",
    "target_class": "package_binary",
    "result": "deny",
    "semantic_outcome": "blocked_expected",
    "explanation_code": "POLICY_EXPECTED_METADATA_BOUNDARY"
  },
  "trust": {
    "mode": "local_first",
    "signature_state": "valid|unsigned|ad_hoc|unknown|invalid|not_applicable",
    "package_origin": "package_manager|system|user_local|container|remote|unknown",
    "content_hash": "sha256:...",
    "attestation_state": "verified|degraded|missing|failed",
    "network_lookup": "not_attempted|blocked_by_policy|allowed|failed|succeeded"
  },
  "noise_control": {
    "event_fingerprint": "fp_...",
    "first_seen": "2026-05-04T19:21:58.369000-04:00",
    "last_seen": "2026-05-04T19:21:58.489000-04:00",
    "count": 1,
    "suppressed_count": 0,
    "coalesce_window_ms": 1000
  },
  "privacy": {
    "tier": "public_summary|user_private|admin_forensic|sealed_secret",
    "redaction_policy": "preserve_causality",
    "secret_fields": []
  },
  "evidence": [
    {
      "evidence_id": "ev_...",
      "source": "kernel|policy-engine|trust-engine|package-db|process-monitor",
      "raw_ref": "immutable-log-offset-or-object-id",
      "summary": "sandbox deny collapsed into expected policy block"
    }
  ],
  "operator_narrative": {
    "summary": "Package-managed shell launched and exited cleanly.",
    "risk": "low",
    "why": "Internal metadata reads were blocked by the sandbox as expected.",
    "next_action": "No action required unless this launch was unexpected."
  },
  "sync": {
    "replication_policy": "local_only|private_mesh|org_controlled|public_demo",
    "retention_class": "ephemeral|standard|forensic|sealed",
    "exportable": false
  }
}
```

## Required invariants

- `event_id` is globally unique.
- `event_class`, `lane`, `severity`, and `outcome` use controlled vocabularies.
- `causality.root_event_id` is stable across derived/coalesced events.
- `privacy.redaction_policy=preserve_causality` must not erase actor/subject relationship shape.
- Raw logs are evidence records, not the operator-facing truth.
- `decision.semantic_outcome` is required for all policy decisions.
- Network trust lookup must be explicit; silent remote trust checks are forbidden.

## Controlled vocabularies

### event_class

- `process.exec`
- `process.exit`
- `policy.decision`
- `trust.evaluation`
- `telemetry.coalesced`
- `operator.narrative`
- `sync.replication`
- `object.repair`
- `schema.validation`
- `agent.action`

### lane

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

### severity

- `trace`
- `debug`
- `info`
- `notice`
- `warning`
- `error`
- `critical`

### outcome

- `allowed`
- `blocked_expected`
- `blocked_unexpected`
- `blocked_attack_like`
- `degraded`
- `failed`

### privacy tier

- `public_summary`
- `user_private`
- `admin_forensic`
- `sealed_secret`

## Example: expected sandbox denial

```json
{
  "event_class": "policy.decision",
  "lane": "policy",
  "severity": "notice",
  "outcome": "blocked_expected",
  "decision": {
    "operation": "file-read-data",
    "target_class": "package_binary_directory",
    "result": "deny",
    "semantic_outcome": "blocked_expected",
    "explanation_code": "POLICY_EXPECTED_METADATA_BOUNDARY"
  },
  "operator_narrative": {
    "summary": "Internal telemetry component was denied direct file reads outside its capability profile.",
    "risk": "low",
    "why": "The component may request package metadata but may not directly read executable directories.",
    "next_action": "No action required."
  }
}
```

## Example: noisy shell launch collapsed

```json
{
  "event_class": "telemetry.coalesced",
  "lane": "process_lifecycle",
  "severity": "notice",
  "outcome": "blocked_expected",
  "noise_control": {
    "event_fingerprint": "fp_shell_launch_policy_blocks",
    "count": 47,
    "suppressed_count": 43,
    "coalesce_window_ms": 1000
  },
  "operator_narrative": {
    "summary": "Package-managed shell launch produced repeated expected policy blocks that were coalesced.",
    "risk": "low",
    "why": "The blocked operations were repeated metadata reads and IPC lookups already covered by baseline policy.",
    "next_action": "No action required unless the shell launch itself was unexpected."
  }
}
```
