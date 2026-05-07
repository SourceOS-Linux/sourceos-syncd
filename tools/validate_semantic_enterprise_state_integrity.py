#!/usr/bin/env python3
"""Validate SourceOS syncd's Semantic Enterprise v0.1 state-integrity mapping fixture."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/semantic-enterprise/v0.1/state-integrity-mapping.example.json"

REQUIRED_SURFACES = {
    "artifact_lineage",
    "release_provenance",
    "repair_lineage",
    "rollback_evidence",
    "local_first_state_context",
    "named_graph_governance",
}
REQUIRED_PROVENANCE = {
    "source_path",
    "graph_uri",
    "source_system",
    "trust_level",
    "access_class",
    "retention_policy",
    "lifecycle_phase",
    "release_tag",
}
REQUIRED_BINDINGS = {
    "release_artifact",
    "state_integrity_report",
    "repair_plan",
    "rollback_evidence",
}
REQUIRED_CLOSURE_KEYS = {
    "inside_source",
    "outside_state_runtime",
    "boundary_membrane",
    "feedback_surface",
}


def main() -> int:
    errors: list[str] = []
    if not FIXTURE.is_file():
        print(f"missing fixture: {FIXTURE}")
        return 1

    try:
        data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"invalid JSON: {exc}")
        return 1

    if data.get("contract") != "sourceos-syncd.semantic-enterprise.state-integrity":
        errors.append("unexpected contract identifier")
    if data.get("version") != "0.1.0":
        errors.append("unexpected contract version")

    source = data.get("source")
    if not isinstance(source, dict):
        errors.append("source must be an object")
    else:
        expected = {
            "repository": "SocioProphet/ontogenesis",
            "release": "semantic-enterprise-v0.1.0",
            "manifest_path": "manifests/semantic_enterprise_v0_1_manifest.json",
            "rollup_registry_path": "catalog/semantic_enterprise_v0_1_registry.ttl",
            "supply_chain_module_path": "Domains/supply-chain.ttl",
            "named_graph_fixture_path": "examples/named-graphs/semantic_sector_named_graphs.ttl",
        }
        for key, value in expected.items():
            if source.get(key) != value:
                errors.append(f"source.{key} expected {value!r}, got {source.get(key)!r}")

    surfaces = set(data.get("state_integrity_surfaces") or [])
    if not REQUIRED_SURFACES.issubset(surfaces):
        errors.append(f"state_integrity_surfaces missing: {sorted(REQUIRED_SURFACES.difference(surfaces))}")

    provenance = set(data.get("provenance_requirements") or [])
    if not REQUIRED_PROVENANCE.issubset(provenance):
        errors.append(f"provenance_requirements missing: {sorted(REQUIRED_PROVENANCE.difference(provenance))}")

    bindings = data.get("semantic_bindings")
    if not isinstance(bindings, list):
        errors.append("semantic_bindings must be a list")
    else:
        binding_surfaces = {binding.get("sourceos_surface") for binding in bindings if isinstance(binding, dict)}
        if binding_surfaces != REQUIRED_BINDINGS:
            errors.append(f"expected sourceos surfaces {sorted(REQUIRED_BINDINGS)}, got {sorted(binding_surfaces)}")
        for binding in bindings:
            if not isinstance(binding, dict):
                errors.append("semantic binding must be an object")
                continue
            surface = binding.get("sourceos_surface")
            if not binding.get("semantic_enterprise_class"):
                errors.append(f"{surface} missing semantic_enterprise_class")
            if not binding.get("evidence_role"):
                errors.append(f"{surface} missing evidence_role")
            required_fields = binding.get("required_fields")
            if not isinstance(required_fields, list) or not required_fields:
                errors.append(f"{surface} must include required_fields")

    contexts = data.get("named_graph_contexts")
    if not isinstance(contexts, list) or not contexts:
        errors.append("named_graph_contexts must be a non-empty list")
    else:
        for context in contexts:
            if not isinstance(context, dict):
                errors.append("named graph context must be an object")
                continue
            if context.get("sector") != "supply-chain":
                errors.append("SourceOS v0.1 mapping should bind the supply-chain sector first")
            if not str(context.get("source_path", "")).startswith("examples/scenarios/"):
                errors.append("named graph context source_path must point to examples/scenarios")
            if not str(context.get("graph_uri_fragment", "")).startswith("graphs/scenarios/"):
                errors.append("named graph context graph_uri_fragment must point to graphs/scenarios")
            for key in ["source_system", "access_class", "trust_level", "retention_policy", "lifecycle_phase"]:
                if not context.get(key):
                    errors.append(f"named graph context missing {key}")

    fixture = data.get("sourceos_fixture")
    if not isinstance(fixture, dict):
        errors.append("sourceos_fixture must be an object")
    else:
        for key in ["artifact_id", "release_tag", "state_context", "graph_uri_fragment", "trust_level", "access_class", "operator_narrative"]:
            if not fixture.get(key):
                errors.append(f"sourceos_fixture missing {key}")
        if fixture.get("release_tag") != "semantic-enterprise-v0.1.0":
            errors.append("sourceos_fixture release_tag mismatch")

    closure = data.get("closure_model")
    if not isinstance(closure, dict):
        errors.append("closure_model must be an object")
    else:
        missing = REQUIRED_CLOSURE_KEYS.difference(closure)
        if missing:
            errors.append(f"closure_model missing keys: {sorted(missing)}")
        for key in REQUIRED_CLOSURE_KEYS.intersection(closure):
            if not isinstance(closure.get(key), str) or not closure[key].strip():
                errors.append(f"closure_model.{key} must be a non-empty string")

    if errors:
        print("Semantic Enterprise state-integrity validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Semantic Enterprise state-integrity validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
