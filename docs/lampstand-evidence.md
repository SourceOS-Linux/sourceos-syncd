# Lampstand Evidence Envelope

Status: v0.1 local stub

`sourceos-syncd` now emits Lampstand-compatible evidence envelopes. The real Lampstand service remains the target evidence plane, but this local writer lets SourceOS preserve reports, policy decisions, repair plans, and scorecards as deterministic JSON artifacts today.

## Purpose

State Integrity Reports should not be transient diagnostics. They should become durable evidence when they influence operator decisions, policy decisions, repair planning, agent trust, or release readiness.

The local evidence writer gives us:

- canonical artifact digests
- deterministic evidence IDs
- an unsigned local attestation shape
- atomic JSON writes
- validation and tamper detection
- a clean replacement path for the real Lampstand service

## Envelope schema

Canonical schema:

```text
schemas/sourceos.lampstand-evidence.v1alpha1.schema.json
```

Envelope shape:

```json
{
  "schema": "sourceos.lampstand-evidence/v1alpha1",
  "evidence_id": "evidence-example",
  "generated_at": "2026-05-05T00:00:00Z",
  "writer": "sourceos-syncd-local-evidence-writer",
  "evidence_type": "policy-decision",
  "subject": "sourceos-syncd",
  "artifact_digest": "sha256:...",
  "artifact": {},
  "attestation": {
    "signed": false,
    "signature": null,
    "reason": "local-stub-unsigned"
  }
}
```

## Supported evidence types

- `state-integrity-report`
- `repair-plan`
- `policy-decision`
- `local-state-summary`
- `agent-trust-decision`
- `delivery-scorecard`

## CLI

Wrap a JSON artifact without writing it:

```bash
sourceos-syncd evidence wrap \
  --file examples/policy/secure-agent-access.decision.json \
  --type policy-decision \
  --subject sourceos-syncd
```

Write an evidence envelope locally:

```bash
sourceos-syncd evidence write \
  --file examples/policy/secure-agent-access.decision.json \
  --type policy-decision \
  --subject sourceos-syncd \
  --output-dir /tmp/sourceos-syncd-evidence
```

Validate an envelope:

```bash
sourceos-syncd evidence validate \
  --file examples/evidence/secure-agent-access.evidence.json
```

## Current behavior

The local writer is deterministic for a given artifact digest, evidence type, subject, and writer. The envelope ID is derived from those values. The artifact digest is computed from canonical JSON.

This lets tests and downstream tooling detect tampering:

- If the artifact changes, the digest check fails.
- If required envelope fields are missing, validation fails.
- If the attestation block is malformed, validation fails.

## Replacement path for real Lampstand

The real Lampstand integration should preserve this envelope shape and replace the local unsigned attestation with a signed record.

Expected future flow:

1. SourceOS component emits a State Integrity Report, policy decision, repair plan, trust decision, or scorecard.
2. `sourceos-syncd` wraps it as `sourceos.lampstand-evidence/v1alpha1`.
3. Lampstand signs the envelope or stores it in an append-only evidence log.
4. AgentPlane and Delivery Excellence consume the evidence URI or digest.
5. Operators can reconstruct what state was trusted, by whom, under which policy, and with what result.

## Security posture

The local stub is not a substitute for signed evidence. It is a compatibility and development bridge. Production-grade evidence requires:

- node identity binding
- signing key management
- append-only storage
- tamper-evident sequencing
- policy-controlled redaction
- replay-resistant timestamps
- cross-component evidence correlation
