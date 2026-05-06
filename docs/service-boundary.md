# SourceOS Syncd Local Service Boundary

Status: MVP service contract
Implementation: `src/sourceos_syncd/service.py`
Console entry point: `sourceos-syncd-service`

## Purpose

`sourceos-syncd-service` exposes a local-only HTTP boundary for the current State Integrity implementation. It is designed for local dashboards, SourceOS shell integrations, Agent-Term, Sherlock/Lampstand collectors, and operator tooling that need structured state without scraping logs.

The CLI remains the stable operator surface. The service mirrors the current report, event, metric, and preview-planning contracts.

## Local-Only Binding

Default bind address:

```bash
sourceos-syncd-service --host 127.0.0.1 --port 8765
```

Supported local bind hosts:

```text
127.0.0.1
localhost
::1
```

Non-local bind hosts are rejected by `ServiceConfig.validate()`.

## Optional Store Root

The service can summarize an explicit local store root:

```bash
sourceos-syncd-service --store-root ./state
```

Every request may also provide a query override:

```text
/statez?store_root=./state
```

## Endpoints

### GET /healthz

Liveness check. Returns process/component identity and version. This endpoint does not imply readiness.

Example response: `examples/service/healthz.json`

### GET /readyz

Readiness check. Distinguishes:

- `healthy`: ready, HTTP 200
- `degraded`: ready but needs attention, HTTP 200
- `unsafe`: not ready, HTTP 503
- `uninitialized`: not ready, HTTP 503
- unknown state: not ready, HTTP 503

Example response: `examples/service/readyz.healthy.json`

### GET /statez

Returns the current State Integrity Report. The response remains compatible with `sourceos.state-integrity-report/v1alpha1`.

Example response: `examples/service/statez.minimal.json`

### GET /events

Returns the local event stream for the selected store root.

Example response: `examples/service/events.json`

### GET /events/{id}

Returns a single event by `event_id`.

Example response: `examples/service/event.evt-00000001.json`

### GET /events/{id}/explain

Returns a compact operator explanation for a single event.

Example response: `examples/service/event-explain.evt-00000001.json`

### GET /metrics

Returns Prometheus/OpenTelemetry-compatible text metrics.

Example response: `examples/service/metrics.txt`

### GET /repairz

Returns a preview-only planning response using the current repair-plan contract. The MVP service does not expose a state-changing repair endpoint.

Example response: `examples/service/repairz.preview.json`

## Current Metrics

The MVP metric names are:

```text
sourceos_syncd_ready
sourceos_syncd_initialized
sourceos_syncd_replay_lag_events
sourceos_syncd_corrupted_objects
sourceos_syncd_ready_http_code
```

## Service Semantics

The service layer must not replace the CLI. The CLI remains the primary operator path for explicit actions. The service layer is a local reporting and preview boundary.

Readiness is not the same as liveness. A process can be live while the local store is uninitialized or state integrity is unsafe.

The service must preserve these rules:

- local-only by default
- no log scraping as API
- no implicit store initialization from read endpoints
- no hidden repair
- no destructive remote operation in the MVP
- structured JSON or metrics text only
- cache disabled with `Cache-Control: no-store`

## Test Coverage

`tests/test_service.py` covers:

- local-only bind validation
- liveness payload shape
- healthy/degraded/unsafe/uninitialized readiness semantics
- local event stream and event lookup
- metrics series generation
- preview-only planning response
- HTTP routes for `/healthz`, `/readyz`, `/statez`, `/events`, `/events/{id}`, `/events/{id}/explain`, `/repairz`, and `/metrics`
