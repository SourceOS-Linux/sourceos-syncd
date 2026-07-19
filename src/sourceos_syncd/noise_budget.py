"""Duplicate suppression and noise-budget engine for sourceos-syncd.

Coalesces repeated low-level events so only operator-meaningful state
changes surface as records. Implements issue sourceos-syncd#8.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _event_key(event: dict[str, Any]) -> str:
    key_fields = {
        "kind": event.get("kind", ""),
        "source": event.get("source", ""),
        "subject_ref": event.get("subjectRef", event.get("subject_ref", "")),
    }
    raw = json.dumps(key_fields, sort_keys=True).encode()
    return hashlib.sha256(raw).hexdigest()[:16]


@dataclass
class NoiseBudgetConfig:
    """Configuration for the noise-budget engine."""

    max_duplicates_per_window: int = 10
    window_seconds: int = 300
    critical_kinds: frozenset[str] = field(default_factory=lambda: frozenset([
        "state-integrity-violation",
        "policy-violation",
        "repair-required",
        "conflict-detected",
        "identity-loss",
    ]))
    exempt_sources: frozenset[str] = field(default_factory=frozenset)


@dataclass
class CoalescedEvent:
    """A coalesced event record with suppression metadata."""

    event: dict[str, Any]
    count: int
    first_seen: str
    last_seen: str
    suppressed_count: int
    key: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": self.event,
            "count": self.count,
            "firstSeen": self.first_seen,
            "lastSeen": self.last_seen,
            "suppressedCount": self.suppressed_count,
            "key": self.key,
        }


@dataclass
class BudgetReport:
    """Noise budget utilization report."""

    window_seconds: int
    total_events_received: int
    unique_events: int
    suppressed_events: int
    budget_utilization: float
    critical_events_passed: int
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "windowSeconds": self.window_seconds,
            "totalEventsReceived": self.total_events_received,
            "uniqueEvents": self.unique_events,
            "suppressedEvents": self.suppressed_events,
            "budgetUtilization": round(self.budget_utilization, 3),
            "criticalEventsPassed": self.critical_events_passed,
            "note": self.note,
        }


class NoiseBudgetEngine:
    """Event coalescer and noise budget enforcer."""

    def __init__(self, config: NoiseBudgetConfig | None = None) -> None:
        self._config = config or NoiseBudgetConfig()
        self._seen: dict[str, CoalescedEvent] = {}
        self._total_received = 0
        self._total_suppressed = 0
        self._critical_passed = 0

    def ingest(self, event: dict[str, Any]) -> CoalescedEvent | None:
        """Ingest an event. Returns the CoalescedEvent if it should surface, None if suppressed."""
        self._total_received += 1
        kind = event.get("kind", "")
        source = event.get("source", "")

        if kind in self._config.critical_kinds or source in self._config.exempt_sources:
            self._critical_passed += 1
            key = _event_key(event)
            coalesced = CoalescedEvent(
                event=event,
                count=1,
                first_seen=_now(),
                last_seen=_now(),
                suppressed_count=0,
                key=key,
            )
            self._seen[key] = coalesced
            return coalesced

        key = _event_key(event)
        if key in self._seen:
            existing = self._seen[key]
            if existing.count >= self._config.max_duplicates_per_window:
                existing.suppressed_count += 1
                self._total_suppressed += 1
                self._seen[key] = existing
                return None
            existing = CoalescedEvent(
                event=event,
                count=existing.count + 1,
                first_seen=existing.first_seen,
                last_seen=_now(),
                suppressed_count=existing.suppressed_count,
                key=key,
            )
            self._seen[key] = existing
            return existing

        coalesced = CoalescedEvent(
            event=event,
            count=1,
            first_seen=_now(),
            last_seen=_now(),
            suppressed_count=0,
            key=key,
        )
        self._seen[key] = coalesced
        return coalesced

    def budget_report(self) -> BudgetReport:
        utilization = self._total_suppressed / max(self._total_received, 1)
        return BudgetReport(
            window_seconds=self._config.window_seconds,
            total_events_received=self._total_received,
            unique_events=len(self._seen),
            suppressed_events=self._total_suppressed,
            budget_utilization=utilization,
            critical_events_passed=self._critical_passed,
        )

    def flush(self) -> None:
        """Reset the window state."""
        self._seen.clear()
        self._total_received = 0
        self._total_suppressed = 0
        self._critical_passed = 0


_default_engine = NoiseBudgetEngine()


def ingest(event: dict[str, Any]) -> CoalescedEvent | None:
    return _default_engine.ingest(event)


def budget_report() -> BudgetReport:
    return _default_engine.budget_report()
