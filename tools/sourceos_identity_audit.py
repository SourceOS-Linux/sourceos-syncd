#!/usr/bin/env python3
"""Audit SourceOS product identity invariants.

This tool compares a service manifest with a hermetic launch manifest and checks
that product identity does not leak upstream engine identity into user-facing or
SourceOS-facing surfaces.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]

UPSTREAM_LEAK_TERMS = {
    "firefox",
    "mozilla",
    "gecko",
    "chromium",
    "chrome",
    "webkit",
}

SHELL_POLLUTION_VARS = {
    "PYTHONPATH",
    "NODE_PATH",
    "GEM_HOME",
    "CARGO_HOME",
    "JAVA_HOME",
    "NIX_PATH",
}


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text())
    except Exception as exc:
        raise SystemExit(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise SystemExit(f"{path}: expected top-level JSON object")
    return obj


def lower(value: Any) -> str:
    return str(value or "").lower()


def has_upstream_leak(value: Any, allowed_terms: set[str] | None = None) -> list[str]:
    allowed_terms = allowed_terms or set()
    text = lower(value)
    return sorted(term for term in UPSTREAM_LEAK_TERMS if term in text and term not in allowed_terms)


def normalized(value: Any) -> str:
    return lower(value).replace("-", "").replace("_", "").replace(".", "")


def audit(service: dict[str, Any], launch: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    product_name = str(launch.get("display_name") or service.get("display_name") or "")
    product_norm = normalized(product_name)

    if service.get("schema_version") != "sourceos.service.v0.1":
        errors.append("service manifest must use schema_version sourceos.service.v0.1")
    if launch.get("schema_version") != "sourceos.launch_manifest.v0.1":
        errors.append("launch manifest must use schema_version sourceos.launch_manifest.v0.1")

    if not product_name:
        errors.append("product display_name is required")

    if service.get("display_name") != launch.get("display_name"):
        errors.append("service display_name must match launch display_name")

    service_id_norm = normalized(service.get("service_id"))
    product_id_norm = normalized(launch.get("product_id"))
    if product_norm and product_norm not in service_id_norm:
        errors.append("service_id should contain normalized product identity")
    if product_norm and product_norm not in product_id_norm:
        errors.append("launch product_id should contain normalized product identity")

    bundle = launch.get("bundle_identity") or {}
    expected_process = str(bundle.get("expected_process_name") or "")
    bundle_id_norm = normalized(bundle.get("bundle_id"))
    if product_norm and product_norm not in bundle_id_norm:
        errors.append("bundle_id should contain normalized product identity")
    if expected_process != product_name:
        errors.append("expected_process_name must equal product display_name")

    invariants = launch.get("identity_invariants") or {}
    for key in ("dock_name", "menu_name", "crash_report_name", "helper_prefix"):
        if invariants.get(key) != product_name:
            errors.append(f"identity_invariants.{key} must equal product display_name")

    profile_policy = str(invariants.get("profile_path_policy") or "")
    if "MUST NOT" not in profile_policy and "must not" not in profile_policy:
        warnings.append("profile_path_policy should explicitly forbid upstream product identity leakage")

    env = launch.get("environment") or {}
    if env.get("inherit_user_shell") is not False:
        errors.append("environment.inherit_user_shell must be false for packaged products")

    path_entries = env.get("path") or []
    if len(path_entries) != len(set(path_entries)):
        errors.append("environment.path must not contain duplicate entries")
    for entry in path_entries:
        if "homebrew" in lower(entry) or "/nix" in lower(entry):
            warnings.append(f"environment.path contains developer/toolchain path: {entry}")

    denied_vars = set(env.get("denied_variables") or [])
    missing_denied = sorted(SHELL_POLLUTION_VARS - denied_vars)
    if missing_denied:
        warnings.append("environment.denied_variables should include: " + ", ".join(missing_denied))

    upstream_engine = str(bundle.get("upstream_engine") or "")
    allowed_in_upstream_field = set(UPSTREAM_LEAK_TERMS)
    surfaces = {
        "service.display_name": service.get("display_name"),
        "launch.display_name": launch.get("display_name"),
        "bundle.expected_process_name": expected_process,
        "identity.dock_name": invariants.get("dock_name"),
        "identity.menu_name": invariants.get("menu_name"),
        "identity.crash_report_name": invariants.get("crash_report_name"),
        "identity.helper_prefix": invariants.get("helper_prefix"),
    }
    for surface, value in surfaces.items():
        leaked = has_upstream_leak(value)
        if leaked:
            errors.append(f"{surface} leaks upstream identity terms: {', '.join(leaked)}")

    if upstream_engine and not has_upstream_leak(upstream_engine, allowed_in_upstream_field):
        warnings.append("bundle.upstream_engine should explicitly document upstream provenance when applicable")

    service_denied_caps = set(((service.get("capabilities") or {}).get("denied") or []))
    if "identity.product.upstream_leak" not in service_denied_caps:
        errors.append("service capabilities.denied must include identity.product.upstream_leak")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit SourceOS product identity invariants")
    parser.add_argument("--service", required=True, help="service manifest JSON path")
    parser.add_argument("--launch", required=True, help="launch manifest JSON path")
    parser.add_argument("--json", action="store_true", help="emit machine-readable audit report")
    args = parser.parse_args()

    service_path = pathlib.Path(args.service)
    launch_path = pathlib.Path(args.launch)
    service = load_json(service_path)
    launch = load_json(launch_path)
    errors, warnings = audit(service, launch)

    report = {
        "service": str(service_path),
        "launch": str(launch_path),
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
    }

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Product identity audit: {report['status']}")
        for warning in warnings:
            print(f"warning: {warning}")
        for error in errors:
            print(f"error: {error}", file=sys.stderr)

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
