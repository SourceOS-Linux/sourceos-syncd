"""Lampstand-compatible evidence writer stubs for sourceos-syncd.

The real Lampstand service will own durable evidence storage and signing. This
module provides a deterministic local envelope and writer so sourceos-syncd can
produce audit-grade artifacts today without taking a dependency on the service.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EVIDENCE_SCHEMA = "sourceos.lampstand-evidence/v1alpha1"
DEFAULT_WRITER = "sourceos-syncd-local-evidence-writer"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def digest_json(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EvidenceEnvelope:
    evidence_id: str
    evidence_type: str
    subject: str
    artifact_digest: str
    artifact: dict[str, Any]
    writer: str = DEFAULT_WRITER
    schema: str = EVIDENCE_SCHEMA
    generated_at: str = field(default_factory=utc_now)
    signed: bool = False
    signature: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "evidence_id": self.evidence_id,
            "generated_at": self.generated_at,
            "writer": self.writer,
            "evidence_type": self.evidence_type,
            "subject": self.subject,
            "artifact_digest": self.artifact_digest,
            "artifact": self.artifact,
            "attestation": {
                "signed": self.signed,
                "signature": self.signature,
                "reason": "local-stub-unsigned" if not self.signed else "signed",
            },
        }


def make_evidence(artifact: dict[str, Any], evidence_type: str, subject: str, writer: str = DEFAULT_WRITER) -> dict[str, Any]:
    artifact_digest = digest_json(artifact)
    seed = {
        "artifact_digest": artifact_digest,
        "evidence_type": evidence_type,
        "subject": subject,
        "writer": writer,
    }
    evidence_id = "evidence-" + hashlib.sha256(canonical_json(seed).encode("utf-8")).hexdigest()[:20]
    return EvidenceEnvelope(
        evidence_id=evidence_id,
        evidence_type=evidence_type,
        subject=subject,
        artifact_digest=artifact_digest,
        artifact=artifact,
        writer=writer,
    ).as_dict()


def validate_evidence(envelope: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {
        "schema",
        "evidence_id",
        "generated_at",
        "writer",
        "evidence_type",
        "subject",
        "artifact_digest",
        "artifact",
        "attestation",
    }
    missing = sorted(required - set(envelope))
    if missing:
        errors.append(f"missing evidence keys: {', '.join(missing)}")
    if envelope.get("schema") != EVIDENCE_SCHEMA:
        errors.append(f"unsupported evidence schema: {envelope.get('schema')!r}")
    if not str(envelope.get("artifact_digest", "")).startswith("sha256:"):
        errors.append("artifact_digest must start with sha256:")
    artifact = envelope.get("artifact")
    if isinstance(artifact, dict) and envelope.get("artifact_digest") != digest_json(artifact):
        errors.append("artifact_digest does not match artifact")
    if not isinstance(envelope.get("attestation"), dict):
        errors.append("attestation must be an object")
    return errors


def write_evidence_file(envelope: dict[str, Any], output_dir: str | Path) -> Path:
    errors = validate_evidence(envelope)
    if errors:
        raise ValueError("invalid evidence envelope: " + "; ".join(errors))
    target_dir = Path(output_dir).expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{envelope['evidence_id']}.json"
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(envelope, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    tmp.replace(target)
    return target


def load_json_file(path: str | Path) -> dict[str, Any]:
    with Path(path).expanduser().open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("evidence artifacts must be JSON objects")
    return data
