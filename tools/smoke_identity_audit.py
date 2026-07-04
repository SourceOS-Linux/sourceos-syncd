#!/usr/bin/env python3
"""Smoke-test SourceOS product identity audit pass/fail behavior."""

from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
AUDIT = ROOT / "tools" / "sourceos_identity_audit.py"
SERVICE = ROOT / "examples" / "services" / "bearbrowser.service.json"
VALID_LAUNCH = ROOT / "examples" / "launch" / "bearbrowser.launch-manifest.json"
INVALID_LAUNCH = ROOT / "examples" / "launch" / "invalid" / "bearbrowser-upstream-leak.launch-manifest.json"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(AUDIT), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def main() -> int:
    valid = run("--service", str(SERVICE), "--launch", str(VALID_LAUNCH))
    if valid.returncode != 0:
        print(valid.stdout)
        print(valid.stderr, file=sys.stderr)
        raise SystemExit("valid BearBrowser identity fixture failed audit")

    invalid = run("--service", str(SERVICE), "--launch", str(INVALID_LAUNCH))
    if invalid.returncode == 0:
        print(invalid.stdout)
        raise SystemExit("invalid upstream identity leak fixture unexpectedly passed audit")

    if "upstream identity" not in invalid.stderr.lower() and "inherit_user_shell" not in invalid.stderr:
        print(invalid.stdout)
        print(invalid.stderr, file=sys.stderr)
        raise SystemExit("invalid identity fixture failed without expected identity/environment diagnostics")

    print("SourceOS product identity audit smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
