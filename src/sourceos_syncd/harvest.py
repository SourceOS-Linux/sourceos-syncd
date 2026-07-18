"""Lawful metadata harvesting bridge for sourceos-syncd.

Binds lawful metadata harvesting to SourceOS import bridge events.
Implements the ProCybernetica harvesting doctrine (PR #59) integration
with sourceos-syncd import events. Implements sourceos-syncd#28.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


HARVEST_CONSENT_BASES = frozenset([
    "explicit-consent",
    "legitimate-interest",
    "legal-obligation",
    "vital-interest",
    "public-task",
    "contract",
])

HARVEST_SCOPES = frozenset([
    "metadata-only",
    "structural-only",
    "content-summary",
    "full-record",
])


@dataclass(frozen=True)
class HarvestEnvelope:
    """A lawful metadata harvest envelope bound to an import bridge event."""

    envelope_ref: str
    source_event_ref: str
    harvest_basis: str
    scope: str
    subject_ref: str
    collector_ref: str
    retention_policy_ref: str
    suppressed_fields: list[str]
    sensitive_data_excluded: bool
    harvested_at: str
    payload_hash: str
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "envelopeRef": self.envelope_ref,
            "sourceEventRef": self.source_event_ref,
            "harvestBasis": self.harvest_basis,
            "scope": self.scope,
            "subjectRef": self.subject_ref,
            "collectorRef": self.collector_ref,
            "retentionPolicyRef": self.retention_policy_ref,
            "suppressedFields": self.suppressed_fields,
            "sensitiveDataExcluded": self.sensitive_data_excluded,
            "harvestedAt": self.harvested_at,
            "payloadHash": self.payload_hash,
            "note": self.note,
        }


@dataclass
class HarvestJournal:
    """Local journal of harvest envelopes for a device."""

    device_ref: str
    envelopes: list[HarvestEnvelope] = field(default_factory=list)
    total: int = 0
    suppressed_count: int = 0
    note: str = "Stub — live harvest bridge deferred to sourceos-syncd daemon per sourceos-syncd#28."

    def to_dict(self) -> dict[str, Any]:
        return {
            "deviceRef": self.device_ref,
            "total": self.total,
            "suppressedCount": self.suppressed_count,
            "envelopes": [e.to_dict() for e in self.envelopes],
            "note": self.note,
        }


SENSITIVE_FIELDS = frozenset([
    "raw_content",
    "credentials",
    "private_key",
    "session_token",
    "password",
    "secret",
    "raw_prompt",
    "kv_cache",
])


def _payload_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def wrap_import_event(
    event: dict[str, Any],
    harvest_basis: str = "legitimate-interest",
    scope: str = "metadata-only",
    collector_ref: str = "urn:srcos:collector:sourceos-syncd:default",
    retention_policy_ref: str = "urn:srcos:retention-policy:default",
) -> HarvestEnvelope:
    """Wrap an import bridge event in a lawful harvest envelope."""
    if harvest_basis not in HARVEST_CONSENT_BASES:
        raise ValueError(f"Unknown harvest basis: {harvest_basis}")
    if scope not in HARVEST_SCOPES:
        raise ValueError(f"Unknown harvest scope: {scope}")

    redacted = {k: v for k, v in event.items() if k not in SENSITIVE_FIELDS}
    suppressed = [k for k in event if k in SENSITIVE_FIELDS]
    payload_hash = _payload_hash(redacted)
    ts = _now()
    envelope_ref = f"urn:srcos:harvest-envelope:{payload_hash[:12]}:{ts.replace(':', '').replace('-', '')[:15]}"

    return HarvestEnvelope(
        envelope_ref=envelope_ref,
        source_event_ref=event.get("id", "unknown"),
        harvest_basis=harvest_basis,
        scope=scope,
        subject_ref=event.get("subjectRef", event.get("subject_ref", "unknown")),
        collector_ref=collector_ref,
        retention_policy_ref=retention_policy_ref,
        suppressed_fields=suppressed,
        sensitive_data_excluded=True,
        harvested_at=ts,
        payload_hash=payload_hash,
    )


def stub_journal(device_ref: str = "unknown") -> HarvestJournal:
    return HarvestJournal(device_ref=device_ref)
