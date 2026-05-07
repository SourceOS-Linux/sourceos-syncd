#!/usr/bin/env python3
"""Registry-backed SourceOS policy decision normalizer.

This tool validates policy explanation-code registries, validates policy
observations, and emits canonical `policy.decision` events whose semantics are
consistent with the registry.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys
import uuid
from typing import Any, Iterable

from jsonschema import Draft202012Validator, FormatChecker

ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTRY_SCHEMA = ROOT / "schemas" / "sourceos.policy-explanation-registry.v0.1.schema.json"
OBSERVATION_SCHEMA = ROOT / "schemas" / "sourceos.policy-observation.v0.1.schema.json"
EVENT_SCHEMA = ROOT / "schemas" / "sourceos.event.v0.1.schema.json"
DEFAULT_REGISTRY = ROOT / "policy" / "explanation-codes.v0.1.json"

SEVERITY_ORDER = {
    "trace": 0,
    "debug": 1,
    "info": 2,
    "notice": 3,
    "warning": 4,
    "error": 5,
    "critical": 6,
}

EVENT_EVIDENCE_SOURCES = {
    "kernel",
    "policy-engine",
    "trust-engine",
    "package-db",
    "process-monitor",
    "sync-engine",
    "operator",
    "agent",
    "raw-log",
    "uploaded-macos-log",
    "uploaded-airport-log",
    "uploaded-console-log",
    "uploaded-crash-report",
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validator_for(schema_path: pathlib.Path) -> Draft202012Validator:
    schema = load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def format_errors(errors: Iterable[Any]) -> list[str]:
    formatted: list[str] = []
    for error in sorted(errors, key=lambda item: list(item.absolute_path)):
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        formatted.append(f"{location}: {error.message}")
    return formatted


def validate_obj(obj: dict[str, Any], schema_path: pathlib.Path) -> list[str]:
    return format_errors(validator_for(schema_path).iter_errors(obj))


def fail(prefix: str, errors: Iterable[str]) -> int:
    for error in errors:
        print(f"{prefix}: {error}", file=sys.stderr)
    return 1


def load_registry(path: pathlib.Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]], list[str]]:
    registry = load_json(path)
    if not isinstance(registry, dict):
        return {}, {}, ["registry must be a JSON object"]

    errors = validate_obj(registry, REGISTRY_SCHEMA)
    if errors:
        return registry, {}, errors

    codes: dict[str, dict[str, Any]] = {}
    duplicate_errors: list[str] = []
    for entry in registry["codes"]:
        code = entry["code"]
        if code in codes:
            duplicate_errors.append(f"duplicate explanation code: {code}")
        codes[code] = entry
    return registry, codes, duplicate_errors


def matches_allowed(value: str, allowed: list[str]) -> bool:
    return "*" in allowed or value in allowed


def stricter_or_equal(candidate: str, baseline: str) -> bool:
    return SEVERITY_ORDER[candidate] >= SEVERITY_ORDER[baseline]


def validate_observation_semantics(obs: dict[str, Any], entry: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if obs["result"] != entry["result"]:
        errors.append(f"result {obs['result']} contradicts registry result {entry['result']} for {entry['code']}")

    if "semantic_outcome" in obs and obs["semantic_outcome"] != entry["semantic_outcome"]:
        errors.append(
            f"semantic_outcome {obs['semantic_outcome']} contradicts registry semantic_outcome {entry['semantic_outcome']} for {entry['code']}"
        )

    if "severity" in obs:
        observed_severity = obs["severity"]
        registry_severity = entry["severity"]
        allow_stricter = bool(entry.get("allow_stricter_severity", True))
        if observed_severity != registry_severity:
            if not allow_stricter:
                errors.append(f"severity {observed_severity} contradicts fixed registry severity {registry_severity} for {entry['code']}")
            elif not stricter_or_equal(observed_severity, registry_severity):
                errors.append(f"severity {observed_severity} is weaker than registry severity {registry_severity} for {entry['code']}")

    if "risk" in obs and obs["risk"] != entry["risk"]:
        # Risk is allowed to be more specific later, but v0.1 keeps it locked so dashboards remain predictable.
        errors.append(f"risk {obs['risk']} contradicts registry risk {entry['risk']} for {entry['code']}")

    if not matches_allowed(obs["operation"], entry["allowed_operation_classes"]):
        errors.append(f"operation {obs['operation']} is not allowed for {entry['code']}")

    if not matches_allowed(obs["target_class"], entry["allowed_target_classes"]):
        errors.append(f"target_class {obs['target_class']} is not allowed for {entry['code']}")

    return errors


def event_evidence(obs: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = obs.get("evidence") or []
    if evidence:
        normalized: list[dict[str, Any]] = []
        for item in evidence:
            source = item.get("source", "raw-log")
            if source not in EVENT_EVIDENCE_SOURCES:
                source = "raw-log"
            normalized.append({
                "evidence_id": item["evidence_id"],
                "source": source,
                "raw_ref": item.get("raw_ref"),
                "summary": item["summary"],
            })
        return normalized

    return [
        {
            "evidence_id": f"ev_{obs['observation_id']}",
            "source": "policy-engine",
            "raw_ref": obs["observation_id"],
            "summary": "Policy decision normalized from registry-backed SourceOS policy observation."
        }
    ]


def normalize_observation(obs: dict[str, Any], entry: dict[str, Any], created_at: str | None = None) -> dict[str, Any]:
    event_id = f"evt_{obs['observation_id']}" if not obs["observation_id"].startswith("evt_") else obs["observation_id"]
    causality = obs.get("causality") or {}
    privacy = obs.get("privacy") or {}

    root_event_id = causality.get("root_event_id") or event_id
    trace_id = causality.get("trace_id") or f"trace_{obs['observation_id']}"
    span_id = causality.get("span_id") or f"span_{uuid.uuid4().hex[:12]}"

    severity = obs.get("severity", entry["severity"])
    outcome = obs.get("semantic_outcome", entry["semantic_outcome"])
    risk = obs.get("risk", entry["risk"])

    return {
        "schema_version": "sourceos.event.v0.1",
        "event_id": event_id,
        "event_class": "policy.decision",
        "lane": "policy",
        "severity": severity,
        "outcome": outcome,
        "created_at": created_at or utc_now(),
        "observed_at_monotonic_ns": 0,
        "host": {
            "host_id": "host_local_pseudonym",
            "platform": "sourceos",
            "kernel": "unknown",
            "privacy_zone": privacy.get("tier", "user_private"),
        },
        "actor": {
            "actor_id": obs["actor"]["actor_id"],
            "actor_type": obs["actor"]["actor_type"],
            "display_name": obs["actor"]["display_name"],
            "uid": obs["actor"].get("uid"),
            "session_id": obs["actor"].get("session_id"),
            "authority_domain": obs["actor"].get("authority_domain"),
        },
        "causality": {
            "parent_event_id": causality.get("parent_event_id"),
            "root_event_id": root_event_id,
            "span_id": span_id,
            "trace_id": trace_id,
        },
        "subject": obs["subject"],
        "decision": {
            "decision_id": f"dec_{obs['observation_id']}",
            "policy_bundle": obs.get("policy_bundle", "sourceos.baseline"),
            "policy_rule": obs.get("policy_rule", f"sourceos.policy.{entry['code'].lower()}"),
            "operation": obs["operation"],
            "target_class": obs["target_class"],
            "result": obs["result"],
            "semantic_outcome": outcome,
            "explanation_code": entry["code"],
        },
        "trust": {
            "mode": "local_first",
            "signature_state": "not_applicable",
            "package_origin": "unknown",
            "content_hash": None,
            "attestation_state": "not_applicable",
            "network_lookup": "not_attempted",
            "degradation_reason": None,
        },
        "noise_control": {
            "event_fingerprint": f"fp_{entry['code'].lower()}_{obs['operation']}_{obs['target_class']}",
            "first_seen": created_at or utc_now(),
            "last_seen": created_at or utc_now(),
            "count": 1,
            "suppressed_count": 0,
            "coalesce_window_ms": 1,
        },
        "privacy": {
            "tier": privacy.get("tier", "user_private"),
            "redaction_policy": privacy.get("redaction_policy", "preserve_causality"),
            "secret_fields": privacy.get("secret_fields", []),
        },
        "evidence": event_evidence(obs),
        "operator_narrative": {
            "summary": obs.get("summary") or entry["default_summary"],
            "risk": risk,
            "why": obs.get("why") or entry["default_why"],
            "next_action": obs.get("next_action") or entry["default_next_action"],
            "drilldown_refs": [item["evidence_id"] for item in event_evidence(obs)],
        },
        "sync": {
            "replication_policy": "local_only",
            "retention_class": "standard",
            "exportable": False,
        },
    }


def load_valid_observation(path: pathlib.Path) -> tuple[dict[str, Any] | None, list[str]]:
    obj = load_json(path)
    if not isinstance(obj, dict):
        return None, ["observation must be a JSON object"]
    errors = validate_obj(obj, OBSERVATION_SCHEMA)
    return obj, errors


def cmd_validate_registry(args: argparse.Namespace) -> int:
    _, codes, errors = load_registry(pathlib.Path(args.registry))
    if errors:
        return fail(args.registry, errors)
    print(f"{args.registry}: valid registry with {len(codes)} codes")
    return 0


def cmd_validate_observation(args: argparse.Namespace) -> int:
    _, codes, registry_errors = load_registry(pathlib.Path(args.registry))
    if registry_errors:
        return fail(args.registry, registry_errors)

    obs, errors = load_valid_observation(pathlib.Path(args.observation))
    if errors or obs is None:
        return fail(args.observation, errors)

    entry = codes.get(obs["explanation_code"])
    if entry is None:
        return fail(args.observation, [f"unknown explanation_code {obs['explanation_code']}"])

    semantic_errors = validate_observation_semantics(obs, entry)
    if semantic_errors:
        return fail(args.observation, semantic_errors)

    print(f"{args.observation}: valid policy observation for {obs['explanation_code']}")
    return 0


def cmd_normalize(args: argparse.Namespace) -> int:
    _, codes, registry_errors = load_registry(pathlib.Path(args.registry))
    if registry_errors:
        return fail(args.registry, registry_errors)

    obs, errors = load_valid_observation(pathlib.Path(args.observation))
    if errors or obs is None:
        return fail(args.observation, errors)

    entry = codes.get(obs["explanation_code"])
    if entry is None:
        return fail(args.observation, [f"unknown explanation_code {obs['explanation_code']}"])

    semantic_errors = validate_observation_semantics(obs, entry)
    if semantic_errors:
        return fail(args.observation, semantic_errors)

    event = normalize_observation(obs, entry, created_at=args.created_at)
    event_errors = validate_obj(event, EVENT_SCHEMA)
    if event_errors:
        return fail("generated policy.decision invalid", event_errors)

    output = json.dumps(event, indent=2, sort_keys=True) + "\n"
    if args.out:
        pathlib.Path(args.out).write_text(output, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(output, end="")
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="SourceOS policy decision normalizer")
    root.add_argument("--registry", default=str(DEFAULT_REGISTRY), help="policy explanation-code registry")
    sub = root.add_subparsers(dest="command", required=True)

    validate_registry = sub.add_parser("validate-registry", help="validate the explanation-code registry")
    validate_registry.set_defaults(func=cmd_validate_registry)

    validate_observation = sub.add_parser("validate-observation", help="validate a policy observation against registry semantics")
    validate_observation.add_argument("observation")
    validate_observation.set_defaults(func=cmd_validate_observation)

    normalize = sub.add_parser("normalize", help="emit a canonical policy.decision event from a policy observation")
    normalize.add_argument("observation")
    normalize.add_argument("--created-at", default="2026-05-04T19:21:58.394000-04:00")
    normalize.add_argument("--out", default=None)
    normalize.set_defaults(func=cmd_normalize)

    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
