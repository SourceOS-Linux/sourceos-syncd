#!/usr/bin/env python3
"""Validate and summarize SourceOS service graph manifests."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import defaultdict
from typing import Any, Iterable

from jsonschema import Draft202012Validator

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVICE_SCHEMA = ROOT / "schemas" / "sourceos-service.schema.json"


def load_json(path: pathlib.Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"{path}: invalid JSON: {exc}") from exc


def validator() -> Draft202012Validator:
    schema = load_json(SERVICE_SCHEMA)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def format_errors(errors: Iterable[Any]) -> list[str]:
    formatted: list[str] = []
    for error in sorted(errors, key=lambda item: list(item.absolute_path)):
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        formatted.append(f"{location}: {error.message}")
    return formatted


def service_paths(patterns: list[str]) -> list[pathlib.Path]:
    paths: list[pathlib.Path] = []
    for pattern in patterns:
        for path in ROOT.glob(pattern):
            if path.is_file():
                paths.append(path)
    return sorted(set(paths))


def load_services(patterns: list[str]) -> tuple[list[tuple[pathlib.Path, dict[str, Any]]], list[str]]:
    svc_validator = validator()
    services: list[tuple[pathlib.Path, dict[str, Any]]] = []
    errors: list[str] = []

    paths = service_paths(patterns)
    if not paths:
        return [], ["no service manifests matched: " + ", ".join(patterns)]

    for path in paths:
        obj = load_json(path)
        if not isinstance(obj, dict):
            errors.append(f"{path}: expected top-level JSON object")
            continue
        validation_errors = format_errors(svc_validator.iter_errors(obj))
        if validation_errors:
            errors.extend(f"{path}: {error}" for error in validation_errors)
            continue
        services.append((path, obj))

    return services, errors


def capability_sets(service: dict[str, Any]) -> dict[str, set[str]]:
    caps = service.get("capabilities") or {}
    return {
        "required": set(caps.get("required") or []),
        "optional": set(caps.get("optional") or []),
        "denied": set(caps.get("denied") or []),
    }


def audit_service(path: pathlib.Path, service: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    service_id = service.get("service_id", str(path))

    caps = capability_sets(service)
    overlap_required_denied = sorted(caps["required"] & caps["denied"])
    overlap_optional_denied = sorted(caps["optional"] & caps["denied"])
    if overlap_required_denied:
        errors.append(f"{service_id}: required capabilities also denied: {', '.join(overlap_required_denied)}")
    if overlap_optional_denied:
        warnings.append(f"{service_id}: optional capabilities also denied: {', '.join(overlap_optional_denied)}")

    if not caps["required"]:
        errors.append(f"{service_id}: must declare at least one required capability")
    if not caps["denied"]:
        warnings.append(f"{service_id}: denied capability set is empty; release gate should be explicit")

    if not service.get("data_classes"):
        errors.append(f"{service_id}: data_classes must be non-empty")
    if not service.get("launch_triggers"):
        errors.append(f"{service_id}: launch_triggers must be non-empty")
    if not service.get("resource_budget"):
        errors.append(f"{service_id}: resource_budget must be non-empty")

    observability = service.get("observability") or {}
    if observability.get("emits_events") is not True:
        errors.append(f"{service_id}: observability.emits_events must be true")
    if observability.get("incident_bundle") is not True:
        errors.append(f"{service_id}: observability.incident_bundle must be true")
    if not observability.get("health_endpoint"):
        warnings.append(f"{service_id}: observability.health_endpoint is empty")

    authority = service.get("authority_domain")
    if authority == "app" and "identity.product.upstream_leak" not in caps["denied"]:
        errors.append(f"{service_id}: app services must deny identity.product.upstream_leak")
    if authority == "app" and "telemetry.emit.remote.default" not in caps["denied"]:
        warnings.append(f"{service_id}: app services should explicitly deny telemetry.emit.remote.default")

    owner = service.get("owner") or {}
    if not owner.get("org") or not owner.get("repo"):
        errors.append(f"{service_id}: owner.org and owner.repo are required")

    return errors, warnings


def graph_summary(services: list[tuple[pathlib.Path, dict[str, Any]]]) -> dict[str, Any]:
    capability_index: dict[str, dict[str, list[str]]] = defaultdict(lambda: {"required_by": [], "optional_for": [], "denied_by": []})
    authority_domains: dict[str, list[str]] = defaultdict(list)
    owners: dict[str, list[str]] = defaultdict(list)

    nodes: list[dict[str, Any]] = []
    for path, service in services:
        service_id = service["service_id"]
        caps = capability_sets(service)
        authority_domains[service["authority_domain"]].append(service_id)
        owner = service.get("owner") or {}
        owner_key = f"{owner.get('org')}/{owner.get('repo')}"
        owners[owner_key].append(service_id)
        nodes.append({
            "service_id": service_id,
            "display_name": service["display_name"],
            "manifest": str(path.relative_to(ROOT)),
            "authority_domain": service["authority_domain"],
            "owner": owner_key,
            "required_capabilities": sorted(caps["required"]),
            "optional_capabilities": sorted(caps["optional"]),
            "denied_capabilities": sorted(caps["denied"]),
            "emits_events": bool((service.get("observability") or {}).get("emits_events")),
            "incident_bundle": bool((service.get("observability") or {}).get("incident_bundle")),
        })
        for cap in caps["required"]:
            capability_index[cap]["required_by"].append(service_id)
        for cap in caps["optional"]:
            capability_index[cap]["optional_for"].append(service_id)
        for cap in caps["denied"]:
            capability_index[cap]["denied_by"].append(service_id)

    return {
        "schema_version": "sourceos.service-graph.v0.1",
        "service_count": len(services),
        "services": nodes,
        "authority_domains": {key: sorted(value) for key, value in sorted(authority_domains.items())},
        "owners": {key: sorted(value) for key, value in sorted(owners.items())},
        "capability_index": {key: {inner: sorted(vals) for inner, vals in value.items()} for key, value in sorted(capability_index.items())},
    }


def cmd_validate(args: argparse.Namespace) -> int:
    services, errors = load_services(args.pattern)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    warning_count = 0
    for path, service in services:
        svc_errors, warnings = audit_service(path, service)
        if svc_errors:
            errors.extend(svc_errors)
        for warning in warnings:
            warning_count += 1
            print(f"warning: {warning}", file=sys.stderr)

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(f"validated {len(services)} SourceOS service manifest(s); warnings={warning_count}")
    return 0


def cmd_graph(args: argparse.Namespace) -> int:
    services, errors = load_services(args.pattern)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    summary = graph_summary(services)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"services: {summary['service_count']}")
        for node in summary["services"]:
            print(f"- {node['service_id']} ({node['authority_domain']}) owner={node['owner']} required={len(node['required_capabilities'])} denied={len(node['denied_capabilities'])}")
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="SourceOS service graph helper")
    sub = root.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="validate and audit service manifests")
    validate.add_argument("pattern", nargs="*", default=["examples/services/*.json"])
    validate.set_defaults(func=cmd_validate)

    graph = sub.add_parser("graph", help="emit service graph summary")
    graph.add_argument("pattern", nargs="*", default=["examples/services/*.json"])
    graph.add_argument("--json", action="store_true")
    graph.set_defaults(func=cmd_graph)

    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
