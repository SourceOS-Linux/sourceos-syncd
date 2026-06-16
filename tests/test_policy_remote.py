from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from sourceos_syncd.policy import POLICY_ENGINE, PolicyRequest, evaluate_policy


def _req(**kwargs) -> PolicyRequest:
    return PolicyRequest(action="read", lane="normal", **kwargs)


def test_local_eval_used_when_no_env_var() -> None:
    with patch("urllib.request.urlopen") as mock_url:
        result = evaluate_policy(_req())
    mock_url.assert_not_called()
    assert result.status in ("allowed", "denied", "deferred", "redacted")
    assert result.engine == POLICY_ENGINE


def test_local_eval_fallback_on_unreachable_remote(monkeypatch) -> None:
    monkeypatch.setenv("SOURCEOS_POLICY_FABRIC_URL", "http://localhost:19999")
    with patch("urllib.request.urlopen", side_effect=ConnectionRefusedError("refused")):
        result = evaluate_policy(_req())
    assert result.status in ("allowed", "denied", "deferred", "redacted")
    assert result.engine == POLICY_ENGINE  # fell back to local


def test_remote_decision_used_when_available(monkeypatch) -> None:
    monkeypatch.setenv("SOURCEOS_POLICY_FABRIC_URL", "http://policy.local")
    remote_payload = {
        "decision_id": "policy-remote-abc",
        "action": "read",
        "lane": "normal",
        "status": "allowed",
        "reason": "remote-allows",
        "subject": "sourceos-syncd",
        "object_id": None,
        "data_class": "internal",
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(remote_payload).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    with patch("urllib.request.urlopen", return_value=mock_resp):
        result = evaluate_policy(_req())
    assert result.decision_id == "policy-remote-abc"
    assert result.reason == "remote-allows"
    assert result.engine == "http://policy.local"


def test_remote_timeout_falls_back_to_local(monkeypatch) -> None:
    monkeypatch.setenv("SOURCEOS_POLICY_FABRIC_URL", "http://policy.local")
    import socket
    with patch("urllib.request.urlopen", side_effect=TimeoutError("timeout")):
        result = evaluate_policy(_req())
    assert result.engine == POLICY_ENGINE  # local fallback


def test_policy_engine_constant_has_no_stub_suffix() -> None:
    assert "stub" not in POLICY_ENGINE


def test_local_eval_still_correct_for_secure_lane(monkeypatch) -> None:
    monkeypatch.delenv("SOURCEOS_POLICY_FABRIC_URL", raising=False)
    result = evaluate_policy(PolicyRequest(action="agent_access", lane="secure"))
    assert result.status == "denied"
    assert result.engine == POLICY_ENGINE
