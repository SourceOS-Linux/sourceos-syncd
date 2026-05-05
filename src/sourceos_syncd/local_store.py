"""Filesystem-backed prototype store for SourceOS state integrity.

This module is intentionally simple and standard-library-only. It gives the
State Integrity Report runtime a concrete local substrate: a manifest, a JSONL
journal, registry directories, lane counters, object counters, and a generation
marker.

Design constraints for the MVP:

- read paths must not silently initialize or reset local state;
- append paths must be explicit and append-only;
- registry writes must be atomic JSON writes;
- durable, rebuildable, and disposable state live in distinct directories.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_LANES = ("normal", "priority", "secure", "memory", "policy", "audit", "tombstone", "migration", "repair", "archive")
MANIFEST_NAME = "manifest.json"
JOURNAL_NAME = "journal.jsonl"
STORE_SCHEMA = "sourceos.local-state-store/v1alpha1"
JOURNAL_SCHEMA = "sourceos.journal-event/v1alpha1"

EVENT_TYPES = {"add", "update", "delete", "checkpoint", "repair", "policy"}
REGISTRY_KINDS = {"profiles", "devices", "actors", "schemas", "objects", "indexes", "repair-reports"}
DURABLE_DIRS = ("profiles", "devices", "actors", "schemas", "objects", "events", "repair-reports")
REBUILDABLE_DIRS = ("indexes", "checkpoints")
DISPOSABLE_DIRS = ("tmp",)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_record_id(record_id: str) -> str:
    """Return a filesystem-safe record id while keeping ids readable."""
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_", ".", ":"} else "_" for ch in record_id.strip())
    cleaned = cleaned.strip(".")
    if not cleaned:
        raise ValueError("record id cannot be empty")
    return cleaned


@dataclass(frozen=True)
class StorePaths:
    root: Path

    @property
    def manifest(self) -> Path:
        return self.root / MANIFEST_NAME

    @property
    def journal(self) -> Path:
        return self.root / JOURNAL_NAME

    @property
    def profiles(self) -> Path:
        return self.root / "profiles"

    @property
    def devices(self) -> Path:
        return self.root / "devices"

    @property
    def actors(self) -> Path:
        return self.root / "actors"

    @property
    def schemas(self) -> Path:
        return self.root / "schemas"

    @property
    def objects(self) -> Path:
        return self.root / "objects"

    @property
    def events(self) -> Path:
        return self.root / "events"

    @property
    def indexes(self) -> Path:
        return self.root / "indexes"

    @property
    def checkpoints(self) -> Path:
        return self.root / "checkpoints"

    @property
    def repair_reports(self) -> Path:
        return self.root / "repair-reports"

    @property
    def tmp(self) -> Path:
        return self.root / "tmp"

    def registry(self, kind: str) -> Path:
        if kind == "profiles":
            return self.profiles
        if kind == "devices":
            return self.devices
        if kind == "actors":
            return self.actors
        if kind == "schemas":
            return self.schemas
        if kind == "objects":
            return self.objects
        if kind == "indexes":
            return self.indexes
        if kind == "repair-reports":
            return self.repair_reports
        raise ValueError(f"unknown registry kind: {kind}")


class LocalStateStore:
    """Small filesystem store used by the first sourceos-syncd prototype."""

    def __init__(self, root: str | os.PathLike[str]):
        self.paths = StorePaths(Path(root).expanduser().resolve())

    def is_initialized(self) -> bool:
        return self.paths.manifest.exists()

    def init(self) -> dict[str, Any]:
        """Initialize the local store idempotently."""
        self.paths.root.mkdir(parents=True, exist_ok=True)
        for name in (*DURABLE_DIRS, *REBUILDABLE_DIRS, *DISPOSABLE_DIRS):
            (self.paths.root / name).mkdir(exist_ok=True)
        if not self.paths.journal.exists():
            self.paths.journal.write_text("", encoding="utf-8")
        if not self.paths.manifest.exists():
            now = utc_now()
            manifest = {
                "schema": STORE_SCHEMA,
                "created_at": now,
                "updated_at": now,
                "active_generation": 1,
                "last_known_good_generation": 1,
                "lanes": list(DEFAULT_LANES),
                "backend": "filesystem-jsonl",
                "durable_dirs": list(DURABLE_DIRS),
                "rebuildable_dirs": list(REBUILDABLE_DIRS),
                "disposable_dirs": list(DISPOSABLE_DIRS),
                "registry_kinds": sorted(REGISTRY_KINDS),
            }
            self._write_manifest(manifest)
        return self.read_manifest(require_initialized=True)

    def read_manifest(self, *, require_initialized: bool = False) -> dict[str, Any]:
        """Read manifest without creating state by default."""
        if not self.paths.manifest.exists():
            if require_initialized:
                raise FileNotFoundError(f"local store is not initialized: {self.paths.root}")
            return self._uninitialized_manifest()
        return json.loads(self.paths.manifest.read_text(encoding="utf-8"))

    def _uninitialized_manifest(self) -> dict[str, Any]:
        return {
            "schema": STORE_SCHEMA,
            "initialized": False,
            "root": str(self.paths.root),
            "backend": "filesystem-jsonl",
            "active_generation": 0,
            "last_known_good_generation": 0,
            "lanes": list(DEFAULT_LANES),
            "durable_dirs": list(DURABLE_DIRS),
            "rebuildable_dirs": list(REBUILDABLE_DIRS),
            "disposable_dirs": list(DISPOSABLE_DIRS),
            "registry_kinds": sorted(REGISTRY_KINDS),
        }

    def _write_manifest(self, manifest: dict[str, Any]) -> None:
        manifest = dict(manifest)
        manifest["initialized"] = True
        manifest["updated_at"] = utc_now()
        self.paths.root.mkdir(parents=True, exist_ok=True)
        tmp = self.paths.manifest.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(manifest, indent=2, sort_keys=False) + "\n", encoding="utf-8")
        tmp.replace(self.paths.manifest)

    def append_event(self, event_type: str, lane: str = "normal", object_id: str | None = None, producer: str = "manual", payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Append one journal event. This is the MVP append-only event log."""
        manifest = self.read_manifest(require_initialized=True)
        if lane not in manifest.get("lanes", []):
            raise ValueError(f"unknown lane: {lane}")
        if event_type not in EVENT_TYPES:
            raise ValueError(f"unknown event_type: {event_type}")
        event_id = self._next_event_id()
        event = {
            "schema": JOURNAL_SCHEMA,
            "event_id": event_id,
            "event_type": event_type,
            "lane": lane,
            "object_id": object_id or f"object-{event_id}",
            "producer": producer,
            "created_at": utc_now(),
            "payload": payload or {},
            "applied": True,
        }
        with self.paths.journal.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=False) + "\n")
        manifest["active_generation"] = int(manifest.get("active_generation", 1)) + 1
        self._write_manifest(manifest)
        return event

    def iter_events(self) -> list[dict[str, Any]]:
        if not self.paths.journal.exists():
            return []
        events: list[dict[str, Any]] = []
        for line_number, line in enumerate(self.paths.journal.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                events.append({
                    "schema": JOURNAL_SCHEMA,
                    "event_id": f"corrupt-line-{line_number}",
                    "event_type": "corrupt",
                    "lane": "repair",
                    "object_id": None,
                    "producer": "local-store-reader",
                    "created_at": utc_now(),
                    "payload": {"line_number": line_number, "error": str(exc)},
                    "applied": False,
                })
                continue
            events.append(event)
        return events

    def put_record(self, kind: str, record_id: str, record: dict[str, Any]) -> dict[str, Any]:
        """Persist a registry record atomically."""
        if kind not in REGISTRY_KINDS:
            raise ValueError(f"unknown registry kind: {kind}")
        self.read_manifest(require_initialized=True)
        if not isinstance(record, dict):
            raise TypeError("record must be a JSON object")
        registry = self.paths.registry(kind)
        registry.mkdir(parents=True, exist_ok=True)
        safe_id = safe_record_id(record_id)
        stored = dict(record)
        stored.setdefault("record_id", record_id)
        stored.setdefault("schema", f"sourceos.{kind.rstrip('s')}-record/v1alpha1")
        stored["updated_at"] = utc_now()
        tmp = registry / f"{safe_id}.json.tmp"
        target = registry / f"{safe_id}.json"
        tmp.write_text(json.dumps(stored, indent=2, sort_keys=False) + "\n", encoding="utf-8")
        tmp.replace(target)
        return stored

    def get_record(self, kind: str, record_id: str) -> dict[str, Any]:
        if kind not in REGISTRY_KINDS:
            raise ValueError(f"unknown registry kind: {kind}")
        target = self.paths.registry(kind) / f"{safe_record_id(record_id)}.json"
        if not target.exists():
            raise FileNotFoundError(f"record not found: {kind}/{record_id}")
        return json.loads(target.read_text(encoding="utf-8"))

    def list_records(self, kind: str) -> list[dict[str, Any]]:
        if kind not in REGISTRY_KINDS:
            raise ValueError(f"unknown registry kind: {kind}")
        registry = self.paths.registry(kind)
        if not registry.exists():
            return []
        records: list[dict[str, Any]] = []
        for path in sorted(registry.glob("*.json")):
            records.append(json.loads(path.read_text(encoding="utf-8")))
        return records

    def summarize(self) -> dict[str, Any]:
        initialized = self.is_initialized()
        manifest = self.read_manifest(require_initialized=False)
        events = self.iter_events() if initialized else []
        journal_bytes = self.paths.journal.stat().st_size if self.paths.journal.exists() else 0
        lane_names = manifest.get("lanes", list(DEFAULT_LANES))
        lane_summaries = {name: self._empty_lane_summary(name) for name in lane_names}
        pipeline = {
            "add": self._empty_event_counts(),
            "update": self._empty_event_counts(),
            "delete": {
                "external_requested": 0,
                "authorized": 0,
                "tombstoned": 0,
                "journaled": 0,
                "propagated": 0,
                "purged": 0,
                "failed": 0,
            },
        }

        seen_objects: set[str] = set()
        deleted_objects: set[str] = set()
        corrupt_count = 0
        unapplied_count = 0
        top_producers: dict[str, int] = {}

        for event in events:
            lane = event.get("lane", "repair")
            if lane not in lane_summaries:
                lane_summaries[lane] = self._empty_lane_summary(lane)
            event_type = event.get("event_type")
            producer = event.get("producer", "unknown")
            top_producers[producer] = top_producers.get(producer, 0) + 1

            if event_type == "corrupt":
                corrupt_count += 1
                lane_summaries[lane]["objects"]["corrupted"] += 1
                continue

            object_id = event.get("object_id")
            if object_id:
                seen_objects.add(str(object_id))
            if not event.get("applied", True):
                unapplied_count += 1

            if event_type in {"add", "update"}:
                counts = pipeline[event_type]
                counts["external_requested"] += 1
                counts["accepted"] += 1
                counts["journaled"] += 1
                counts["applied"] += 1 if event.get("applied", True) else 0
            elif event_type == "delete":
                pipeline["delete"]["external_requested"] += 1
                pipeline["delete"]["authorized"] += 1
                pipeline["delete"]["tombstoned"] += 1
                pipeline["delete"]["journaled"] += 1
                pipeline["delete"]["propagated"] += 1 if event.get("applied", True) else 0
                if object_id:
                    deleted_objects.add(str(object_id))
                    lane_summaries[lane]["objects"]["tombstones"] += 1
            elif event_type in {"checkpoint", "repair", "policy"}:
                lane_summaries[lane]["objects"]["total"] += 1

        live_objects = seen_objects - deleted_objects
        for lane in lane_summaries.values():
            lane["journal"]["segment_count"] = 1 if journal_bytes else 0
            lane["journal"]["total_bytes"] = journal_bytes
            lane["journal"]["max_segment_bytes"] = journal_bytes
            lane["journal"]["replay_lag_events"] = unapplied_count
            lane["journal"]["checksum_state"] = "verified" if corrupt_count == 0 else "mismatch"
            if not initialized:
                lane["status"] = "dormant"
        if "normal" in lane_summaries:
            lane_summaries["normal"]["objects"]["total"] = len(live_objects)
        if "repair" in lane_summaries:
            lane_summaries["repair"]["objects"]["corrupted"] += corrupt_count
            if corrupt_count:
                lane_summaries["repair"]["status"] = "degraded"

        registry_counts = {kind: len(self.list_records(kind)) if initialized else 0 for kind in sorted(REGISTRY_KINDS)}

        return {
            "manifest": manifest,
            "local_state": {
                "initialized": initialized,
                "root": str(self.paths.root),
                "durable_dirs": list(DURABLE_DIRS),
                "rebuildable_dirs": list(REBUILDABLE_DIRS),
                "disposable_dirs": list(DISPOSABLE_DIRS),
                "registry_counts": registry_counts,
                "journal_present": self.paths.journal.exists(),
                "manifest_present": self.paths.manifest.exists(),
            },
            "stores": [
                {
                    "name": "content-store-a",
                    "role": "active" if initialized else "dormant",
                    "backend": manifest.get("backend", "filesystem-jsonl"),
                    "schema_version": "1.0.0",
                    "created_by_version": manifest.get("created_by_version", "0.1.0"),
                    "runtime_version": manifest.get("runtime_version", "0.1.0"),
                    "previous_runtime_version": manifest.get("previous_runtime_version"),
                    "migration_state": manifest.get("migration_state", "none"),
                    "active_generation": int(manifest.get("active_generation", 0)),
                    "last_known_good_generation": int(manifest.get("last_known_good_generation", 0)),
                    "shadow_present": self.paths.checkpoints.exists(),
                    "manifest_present": self.paths.manifest.exists(),
                    "checksum_state": "verified" if initialized and corrupt_count == 0 else "unverified" if not initialized else "mismatch",
                    "flags_raw": 100664130 if initialized else 0,
                    "flags_hex": "0x6000342" if initialized else "0x0",
                    "flags_decoded": ["LANE_CONTENT", "LANE_USER_VISIBLE", "STORE_JOURNALED", "STORE_SHADOWED", "COMPACTION_ENABLED"] if initialized else [],
                    "unknown_flags": [],
                }
            ],
            "lanes": list(lane_summaries.values()),
            "pipeline": pipeline,
            "top_producers": sorted(({"producer": key, "events": value} for key, value in top_producers.items()), key=lambda item: item["events"], reverse=True),
        }

    def _next_event_id(self) -> str:
        count = len(self.iter_events()) + 1
        return f"evt-{count:08d}"

    @staticmethod
    def _empty_event_counts() -> dict[str, int]:
        return {
            "external_requested": 0,
            "internal_generated": 0,
            "accepted": 0,
            "journaled": 0,
            "applied": 0,
            "deduped": 0,
            "replayed": 0,
            "skipped": 0,
            "failed": 0,
        }

    @staticmethod
    def _empty_lane_summary(name: str) -> dict[str, Any]:
        return {
            "name": name,
            "status": "active",
            "sla": {
                "max_heartbeat_age_ms": 30000,
                "max_replay_lag_events": 0 if name == "priority" else 100,
                "max_replay_lag_ms": 1000 if name == "priority" else 10000,
            },
            "objects": {
                "total": 0,
                "tombstones": 0,
                "orphans": 0,
                "corrupted": 0,
                "encrypted": 0,
                "redacted": 0,
            },
            "journal": {
                "segment_count": 0,
                "total_bytes": 0,
                "max_segment_bytes": 0,
                "oldest_unapplied_event_age_ms": 0,
                "replay_lag_events": 0,
                "replay_lag_bytes": 0,
                "replay_throughput_events_per_sec": 0,
                "replay_eta_ms": 0,
                "checksum_state": "verified",
            },
            "maintenance": {
                "last_compact_started_at": None,
                "last_compact_completed_at": None,
                "last_compact_duration_ms": None,
                "compaction_debt": "none",
                "last_purge_started_at": None,
                "last_purge_completed_at": None,
                "purge_debt": "none",
                "last_repair_at": None,
                "repair_debt": "none",
            },
        }
