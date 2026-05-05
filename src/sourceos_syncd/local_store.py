"""Filesystem-backed prototype store for SourceOS state integrity.

This module is intentionally simple and standard-library-only. It gives the
State Integrity Report runtime a concrete local substrate: a manifest, a JSONL
journal, lane counters, object counters, and a generation marker.
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


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
    def objects(self) -> Path:
        return self.root / "objects"

    @property
    def checkpoints(self) -> Path:
        return self.root / "checkpoints"


class LocalStateStore:
    """Small filesystem store used by the first sourceos-syncd prototype."""

    def __init__(self, root: str | os.PathLike[str]):
        self.paths = StorePaths(Path(root).expanduser().resolve())

    def init(self) -> dict[str, Any]:
        self.paths.root.mkdir(parents=True, exist_ok=True)
        self.paths.objects.mkdir(exist_ok=True)
        self.paths.checkpoints.mkdir(exist_ok=True)
        if not self.paths.journal.exists():
            self.paths.journal.write_text("", encoding="utf-8")
        if not self.paths.manifest.exists():
            manifest = {
                "schema": "sourceos.local-state-store/v1alpha1",
                "created_at": utc_now(),
                "updated_at": utc_now(),
                "active_generation": 1,
                "last_known_good_generation": 1,
                "lanes": list(DEFAULT_LANES),
                "backend": "filesystem-jsonl",
            }
            self._write_manifest(manifest)
        return self.read_manifest()

    def read_manifest(self) -> dict[str, Any]:
        if not self.paths.manifest.exists():
            return self.init()
        return json.loads(self.paths.manifest.read_text(encoding="utf-8"))

    def _write_manifest(self, manifest: dict[str, Any]) -> None:
        manifest = dict(manifest)
        manifest["updated_at"] = utc_now()
        self.paths.root.mkdir(parents=True, exist_ok=True)
        tmp = self.paths.manifest.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(manifest, indent=2, sort_keys=False) + "\n", encoding="utf-8")
        tmp.replace(self.paths.manifest)

    def append_event(self, event_type: str, lane: str = "normal", object_id: str | None = None, producer: str = "manual", payload: dict[str, Any] | None = None) -> dict[str, Any]:
        manifest = self.read_manifest()
        if lane not in manifest.get("lanes", []):
            raise ValueError(f"unknown lane: {lane}")
        if event_type not in {"add", "update", "delete", "checkpoint", "repair", "policy"}:
            raise ValueError(f"unknown event_type: {event_type}")
        event = {
            "schema": "sourceos.journal-event/v1alpha1",
            "event_id": self._next_event_id(),
            "event_type": event_type,
            "lane": lane,
            "object_id": object_id or f"object-{self._next_event_id()}",
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
                    "schema": "sourceos.journal-event/v1alpha1",
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

    def summarize(self) -> dict[str, Any]:
        manifest = self.read_manifest()
        events = self.iter_events()
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
        if "normal" in lane_summaries:
            lane_summaries["normal"]["objects"]["total"] = len(live_objects)
        if "repair" in lane_summaries:
            lane_summaries["repair"]["objects"]["corrupted"] += corrupt_count
            if corrupt_count:
                lane_summaries["repair"]["status"] = "degraded"

        return {
            "manifest": manifest,
            "stores": [
                {
                    "name": "content-store-a",
                    "role": "active",
                    "backend": manifest.get("backend", "filesystem-jsonl"),
                    "schema_version": "1.0.0",
                    "created_by_version": manifest.get("created_by_version", "0.1.0"),
                    "runtime_version": manifest.get("runtime_version", "0.1.0"),
                    "previous_runtime_version": manifest.get("previous_runtime_version"),
                    "migration_state": manifest.get("migration_state", "none"),
                    "active_generation": int(manifest.get("active_generation", 1)),
                    "last_known_good_generation": int(manifest.get("last_known_good_generation", 1)),
                    "shadow_present": self.paths.checkpoints.exists(),
                    "manifest_present": self.paths.manifest.exists(),
                    "checksum_state": "verified" if corrupt_count == 0 else "mismatch",
                    "flags_raw": 100664130,
                    "flags_hex": "0x6000342",
                    "flags_decoded": ["LANE_CONTENT", "LANE_USER_VISIBLE", "STORE_JOURNALED", "STORE_SHADOWED", "COMPACTION_ENABLED"],
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
