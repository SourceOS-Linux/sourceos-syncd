from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from sourceos_syncd.local_store import LocalStateStore
from sourceos_syncd.service import (
    ServiceConfig,
    events_from_store,
    find_event,
    liveness,
    make_handler,
    metrics_text,
    planning_preview,
    readiness_from_report,
    snapshot_from_store,
)


def test_service_config_rejects_non_local_bind_host() -> None:
    with pytest.raises(ValueError, match="local-only"):
        ServiceConfig(host="0.0.0.0").validate()


def test_liveness_payload_is_stable() -> None:
    payload = liveness()

    assert payload["live"] is True
    assert payload["component"] == "sourceos-syncd"
    assert "version" in payload
    assert "generated_at" in payload


def test_readiness_distinguishes_uninitialized_store(tmp_path: Path) -> None:
    report = snapshot_from_store(tmp_path / "missing-store")
    code, payload = readiness_from_report(report)

    assert code == int(HTTPStatus.SERVICE_UNAVAILABLE)
    assert payload["ready"] is False
    assert payload["status"] == "uninitialized"


def test_readiness_allows_degraded_report() -> None:
    report = {
        "diagnosis": {
            "status": "degraded",
            "severity": "warning",
            "summary": "Fixture degraded state.",
        }
    }
    code, payload = readiness_from_report(report)

    assert code == int(HTTPStatus.OK)
    assert payload["ready"] is True
    assert payload["status"] == "degraded"


def test_readiness_blocks_unsafe_report() -> None:
    report = {
        "diagnosis": {
            "status": "unsafe",
            "severity": "critical",
            "summary": "Fixture unsafe state.",
        }
    }
    code, payload = readiness_from_report(report)

    assert code == int(HTTPStatus.SERVICE_UNAVAILABLE)
    assert payload["ready"] is False
    assert payload["status"] == "unsafe"


def test_events_and_event_lookup_from_store(tmp_path: Path) -> None:
    store = LocalStateStore(tmp_path)
    store.init()
    event = store.append_event("add", object_id="object:alpha", producer="pytest")

    assert events_from_store(str(tmp_path)) == [event]
    assert find_event(event["event_id"], str(tmp_path)) == event
    assert find_event("missing", str(tmp_path)) is None


def test_metrics_text_contains_core_series(tmp_path: Path) -> None:
    store = LocalStateStore(tmp_path)
    store.init()
    store.append_event("add", object_id="object:alpha", producer="pytest")
    report = snapshot_from_store(tmp_path)

    metrics = metrics_text(report)

    assert "sourceos_syncd_ready" in metrics
    assert "sourceos_syncd_initialized 1" in metrics
    assert "sourceos_syncd_replay_lag_events" in metrics
    assert "sourceos_syncd_corrupted_objects" in metrics


def test_planning_preview_is_preview_only(tmp_path: Path) -> None:
    store = LocalStateStore(tmp_path)
    store.init()
    plan = planning_preview(str(tmp_path))

    assert plan["schema"] == "sourceos.repair-plan/v1alpha1"
    assert plan["status"] == "preview"
    assert plan["service"]["preview_only"] is True
    assert plan["policy"]["destructive_actions_present"] is False


def get_json(port: int, path: str) -> tuple[int, dict]:
    connection = HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        data = json.loads(response.read().decode("utf-8"))
        return response.status, data
    finally:
        connection.close()


def get_text(port: int, path: str) -> tuple[int, str]:
    connection = HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        data = response.read().decode("utf-8")
        return response.status, data
    finally:
        connection.close()


def test_http_routes_expose_local_service_boundary(tmp_path: Path) -> None:
    store = LocalStateStore(tmp_path)
    store.init()
    event = store.append_event("add", object_id="object:alpha", producer="pytest")

    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(ServiceConfig(store_root=str(tmp_path))))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        code, health = get_json(port, "/healthz")
        assert code == int(HTTPStatus.OK)
        assert health["live"] is True

        code, ready = get_json(port, "/readyz")
        assert code == int(HTTPStatus.OK)
        assert ready["ready"] is True

        code, state = get_json(port, "/statez")
        assert code == int(HTTPStatus.OK)
        assert state["schema"] == "sourceos.state-integrity-report/v1alpha1"
        assert state["local_state"]["initialized"] is True

        code, events = get_json(port, "/events")
        assert code == int(HTTPStatus.OK)
        assert events["events"][0]["event_id"] == event["event_id"]

        code, event_payload = get_json(port, f"/events/{event['event_id']}")
        assert code == int(HTTPStatus.OK)
        assert event_payload["event_id"] == event["event_id"]

        code, explanation = get_json(port, f"/events/{event['event_id']}/explain")
        assert code == int(HTTPStatus.OK)
        assert explanation["event_id"] == event["event_id"]
        assert explanation["actor_or_producer"] == "pytest"

        code, missing = get_json(port, "/events/missing")
        assert code == int(HTTPStatus.NOT_FOUND)
        assert missing["error"] == "not_found"

        code, repair = get_json(port, "/repairz")
        assert code == int(HTTPStatus.OK)
        assert repair["status"] == "preview"
        assert repair["service"]["preview_only"] is True

        code, metrics = get_text(port, "/metrics")
        assert code == int(HTTPStatus.OK)
        assert "sourceos_syncd_ready" in metrics
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
