from __future__ import annotations

import copy
import json

from sourceos_syncd.evidence import digest_json, make_evidence, validate_evidence, write_evidence_file


def test_evidence_wraps_artifact_with_digest():
    artifact = {
        "schema": "sourceos.state-integrity-report/v1alpha1",
        "identity": {"component": "sourceos-syncd"},
    }
    envelope = make_evidence(artifact, "state-integrity-report", "sourceos-syncd")
    assert envelope["schema"] == "sourceos.lampstand-evidence/v1alpha1"
    assert envelope["artifact_digest"] == digest_json(artifact)
    assert envelope["attestation"]["signed"] is False
    assert validate_evidence(envelope) == []


def test_evidence_validation_detects_tampering():
    artifact = {"schema": "sourceos.policy-decision/v1alpha1", "status": "allowed"}
    envelope = make_evidence(artifact, "policy-decision", "sourceos-syncd")
    tampered = copy.deepcopy(envelope)
    tampered["artifact"]["status"] = "denied"
    errors = validate_evidence(tampered)
    assert any("artifact_digest does not match artifact" in error for error in errors)


def test_evidence_file_writer_is_valid_json(tmp_path):
    artifact = {"schema": "sourceos.repair-plan/v1alpha1", "status": "preview"}
    envelope = make_evidence(artifact, "repair-plan", "sourceos-syncd")
    path = write_evidence_file(envelope, tmp_path)
    assert path.exists()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["evidence_id"] == envelope["evidence_id"]
    assert validate_evidence(loaded) == []
