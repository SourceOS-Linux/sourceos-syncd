from __future__ import annotations

import json
from pathlib import Path

from sourceos_syncd.evidence import validate_evidence
from sourceos_syncd.policy import POLICY_DECISION_SCHEMA
from sourceos_syncd.trust import validate_trust_decision

ROOT = Path(__file__).resolve().parents[1]


def load(path: str):
    with open(ROOT / path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def test_policy_fixture_shape():
    decision = load("examples/policy/secure-agent-access.decision.json")
    assert decision["schema"] == POLICY_DECISION_SCHEMA
    assert decision["status"] == "denied"
    assert decision["reason"] == "secure_lane_requires_explicit_grant"


def test_evidence_fixture_validates_digest():
    envelope = load("examples/evidence/secure-agent-access.evidence.json")
    assert validate_evidence(envelope) == []


def test_trust_fixture_validates():
    decision = load("examples/trust/normal-read.allowed.json")
    assert validate_trust_decision(decision) == []
