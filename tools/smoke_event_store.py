#!/usr/bin/env python3
"""Smoke-test the local SourceOS canonical event store CLI."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
EVENTCTL = ROOT / "tools" / "sourceos_eventctl.py"
FIXTURE = ROOT / "examples" / "events" / "apple-mdm-entitlement-denial.coalesced.json"


def run(*args: str, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(EVENTCTL), *args],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="sourceos-event-store-") as temp:
        store = pathlib.Path(temp) / "events.jsonl"

        run("write", str(FIXTURE), "--store", str(store))
        run(
            "emit-policy-decision",
            "--actor",
            "sourceos-policy-engine",
            "--subject",
            "com.example.target",
            "--policy-rule",
            "sourceos.example.deny",
            "--operation",
            "ipc.lookup.example",
            "--target-class",
            "example_ipc_service",
            "--explanation-code",
            "POLICY_EXPECTED_TEST_BOUNDARY",
            "--summary",
            "Example expected policy boundary was enforced.",
            "--why",
            "This smoke test proves generated policy-decision events validate against the canonical schema.",
            "--next-action",
            "No action required.",
            "--store",
            str(store),
        )

        listed = run("list", "--store", str(store), "--fail-empty", capture=True).stdout
        if "evt_apple_mdm_entitlement_denial_coalesced" not in listed:
            raise SystemExit("seed event missing from event store list output")

        fixture_event = json.loads(FIXTURE.read_text())
        shown = run("show", fixture_event["event_id"], "--store", str(store), capture=True).stdout
        if json.loads(shown)["event_id"] != fixture_event["event_id"]:
            raise SystemExit("show returned the wrong event")

        verify = run("verify-store", "--store", str(store), "--fail-empty", capture=True).stdout
        if "verified 2 events" not in verify:
            raise SystemExit(f"unexpected verify output: {verify}")

    print("SourceOS event store smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
