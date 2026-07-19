"""Local-only HTTP service boundary for sourceos-syncd.

The service is standard-library-only and exposes read/preview endpoints for the
current State Integrity Report implementation. The CLI remains the stable
operator surface.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from . import __version__
from .local_store import LocalStateStore
from .reports import repair_plan, snapshot, utc_now
from .store_reports import snapshot_from_store

LOCAL_BIND_HOSTS = {"127.0.0.1", "localhost", "::1"}


def json_bytes(payload: dict[str, Any] | list[Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=False) + "\n").encode("utf-8")


def build_state_report(store_root: str | None = None) -> dict[str, Any]:
    return snapshot_from_store(store_root) if store_root else snapshot()


def readiness_from_report(report: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    diagnosis = report.get("diagnosis", {}) if isinstance(report.get("diagnosis"), dict) else {}
    local_state = report.get("local_state") or diagnosis.get("local_state") or {}
    initialized = local_state.get("initialized")
    status = diagnosis.get("status", "unknown")
    severity = diagnosis.get("severity", "unknown")

    if initialized is False:
        return int(HTTPStatus.SERVICE_UNAVAILABLE), {
            "ready": False,
            "status": "uninitialized",
            "severity": "warning",
            "summary": "Local state store is not initialized.",
            "generated_at": utc_now(),
        }

    if status == "healthy":
        code, ready = HTTPStatus.OK, True
    elif status == "degraded":
        code, ready = HTTPStatus.OK, True
    elif status == "unsafe":
        code, ready = HTTPStatus.SERVICE_UNAVAILABLE, False
    else:
        code, ready = HTTPStatus.SERVICE_UNAVAILABLE, False

    return int(code), {
        "ready": ready,
        "status": status,
        "severity": severity,
        "summary": diagnosis.get("summary", "State Integrity readiness is unknown."),
        "generated_at": utc_now(),
    }


def liveness() -> dict[str, Any]:
    return {"live": True, "component": "sourceos-syncd", "version": __version__, "generated_at": utc_now()}


def events_from_store(store_root: str | None = None) -> list[dict[str, Any]]:
    if not store_root:
        return []
    return LocalStateStore(store_root).iter_events()


def find_event(event_id: str, store_root: str | None = None) -> dict[str, Any] | None:
    for event in events_from_store(store_root):
        if event.get("event_id") == event_id:
            return event
    return None


def explain_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": event.get("event_id"),
        "event_type": event.get("event_type"),
        "summary": f"Event {event.get('event_id')} recorded {event.get('event_type')} on lane {event.get('lane', 'unknown')}.",
        "actor_or_producer": event.get("producer") or event.get("actor_id"),
        "object_id": event.get("object_id"),
        "created_at": event.get("created_at") or event.get("occurred_at"),
    }


def planning_preview(store_root: str | None = None) -> dict[str, Any]:
    report = build_state_report(store_root)
    plan = repair_plan(report)
    plan.setdefault("service", {})["preview_only"] = True
    return plan


def metrics_text(report: dict[str, Any]) -> str:
    diagnosis = report.get("diagnosis", {}) if isinstance(report.get("diagnosis"), dict) else {}
    status = diagnosis.get("status", "unknown")
    local_state = report.get("local_state") or diagnosis.get("local_state") or {}
    initialized = 1 if local_state.get("initialized", True) is not False else 0
    corrupted = sum(int(lane.get("objects", {}).get("corrupted", 0) or 0) for lane in report.get("lanes", []) if isinstance(lane, dict))
    replay_lag = sum(int(lane.get("journal", {}).get("replay_lag_events", 0) or 0) for lane in report.get("lanes", []) if isinstance(lane, dict))
    ready_code, ready = readiness_from_report(report)
    ready_value = 1 if ready.get("ready") else 0
    return "\n".join([
        "# HELP sourceos_syncd_ready SourceOS syncd readiness, 1 when ready.",
        "# TYPE sourceos_syncd_ready gauge",
        f"sourceos_syncd_ready{{status=\"{status}\"}} {ready_value}",
        "# HELP sourceos_syncd_initialized Local state initialization status.",
        "# TYPE sourceos_syncd_initialized gauge",
        f"sourceos_syncd_initialized {initialized}",
        "# HELP sourceos_syncd_replay_lag_events Total replay lag events across lanes.",
        "# TYPE sourceos_syncd_replay_lag_events gauge",
        f"sourceos_syncd_replay_lag_events {replay_lag}",
        "# HELP sourceos_syncd_corrupted_objects Corrupted object count across lanes.",
        "# TYPE sourceos_syncd_corrupted_objects gauge",
        f"sourceos_syncd_corrupted_objects {corrupted}",
        "# HELP sourceos_syncd_ready_http_code HTTP code selected by readiness computation.",
        "# TYPE sourceos_syncd_ready_http_code gauge",
        f"sourceos_syncd_ready_http_code {ready_code}",
        "",
    ])


@dataclass(frozen=True)
class ServiceConfig:
    host: str = "127.0.0.1"
    port: int = 8765
    store_root: str | None = None

    def validate(self) -> None:
        if self.host not in LOCAL_BIND_HOSTS:
            raise ValueError(f"sourceos-syncd service is local-only; refusing bind host {self.host!r}")


def make_handler(config: ServiceConfig) -> type[BaseHTTPRequestHandler]:
    config.validate()

    class SourceOSSyncdHandler(BaseHTTPRequestHandler):
        server_version = "sourceos-syncd/" + __version__

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            query = parse_qs(parsed.query)
            store_root = query.get("store_root", [config.store_root])[0]
            try:
                if path == "/healthz":
                    self.write_json(HTTPStatus.OK, liveness())
                elif path == "/readyz":
                    code, payload = readiness_from_report(build_state_report(store_root))
                    self.write_json(code, payload)
                elif path == "/statez":
                    self.write_json(HTTPStatus.OK, build_state_report(store_root))
                elif path == "/events":
                    self.write_json(HTTPStatus.OK, {"events": events_from_store(store_root)})
                elif path.startswith("/events/"):
                    self.handle_event_path(path, store_root)
                elif path == "/metrics":
                    self.write_text(HTTPStatus.OK, metrics_text(build_state_report(store_root)), "text/plain; charset=utf-8")
                elif path == "/repairz":
                    self.write_json(HTTPStatus.OK, planning_preview(store_root))
                elif path == "/noisez":
                    from sourceos_syncd.noise_budget import budget_report
                    self.write_json(HTTPStatus.OK, budget_report().to_dict())
                elif path == "/narrativez":
                    from sourceos_syncd.narrative import stub_narrative
                    report = build_state_report(store_root)
                    from sourceos_syncd.narrative import narrative_from_report
                    narr = narrative_from_report(report)
                    self.write_json(HTTPStatus.OK, narr.to_dict())
                elif path == "/coherencez":
                    from sourceos_syncd.coherence import stub_snapshot
                    self.write_json(HTTPStatus.OK, stub_snapshot().to_dict())
                elif path == "/authorityz":
                    from sourceos_syncd.authority import stub_report
                    self.write_json(HTTPStatus.OK, stub_report().to_dict())
                else:
                    self.write_json(HTTPStatus.NOT_FOUND, {"error": "not_found", "path": path})
            except Exception as exc:  # noqa: BLE001
                self.write_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": type(exc).__name__, "message": str(exc)})

        def handle_event_path(self, path: str, store_root: str | None) -> None:
            parts = path.strip("/").split("/")
            event_id = parts[1] if len(parts) >= 2 else ""
            event = find_event(event_id, store_root)
            if event is None:
                self.write_json(HTTPStatus.NOT_FOUND, {"error": "not_found", "event_id": event_id})
            elif len(parts) == 3 and parts[2] == "explain":
                self.write_json(HTTPStatus.OK, explain_event(event))
            elif len(parts) == 2:
                self.write_json(HTTPStatus.OK, event)
            else:
                self.write_json(HTTPStatus.NOT_FOUND, {"error": "not_found", "path": path})

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

        def write_json(self, status: int | HTTPStatus, payload: dict[str, Any] | list[Any]) -> None:
            body = json_bytes(payload)
            self.send_response(int(status))
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def write_text(self, status: int | HTTPStatus, payload: str, content_type: str) -> None:
            body = payload.encode("utf-8")
            self.send_response(int(status))
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return SourceOSSyncdHandler


def run_service(config: ServiceConfig) -> None:
    config.validate()
    server = ThreadingHTTPServer((config.host, config.port), make_handler(config))
    try:
        server.serve_forever()
    finally:
        server.server_close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sourceos_syncd.service", description="Run local-only sourceos-syncd HTTP service.")
    parser.add_argument("--host", default="127.0.0.1", help="local bind host; defaults to 127.0.0.1")
    parser.add_argument("--port", type=int, default=8765, help="local bind port")
    parser.add_argument("--store-root", help="optional local store root")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_service(ServiceConfig(host=args.host, port=args.port, store_root=args.store_root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
