# Semantic Enterprise State Integrity Mapping v0.1

`sourceos-syncd` consumes `semantic-enterprise-v0.1.0` from `SocioProphet/ontogenesis` as a state-integrity mapping surface.

The local fixture is:

- `examples/semantic-enterprise/v0.1/state-integrity-mapping.example.json`

The validator is:

- `tools/validate_semantic_enterprise_state_integrity.py`

## Source release

- Repository: `SocioProphet/ontogenesis`
- Release/tag: `semantic-enterprise-v0.1.0`
- Manifest: `manifests/semantic_enterprise_v0_1_manifest.json`
- Rollup registry: `catalog/semantic_enterprise_v0_1_registry.ttl`
- Supply-chain module: `Domains/supply-chain.ttl`
- Named graph fixture: `examples/named-graphs/semantic_sector_named_graphs.ttl`

## State integrity surfaces

The v0.1 mapping covers:

- artifact lineage
- release provenance
- repair lineage
- rollback evidence
- local-first state context
- named graph governance

## Semantic bindings

The fixture maps SourceOS state surfaces to Semantic Enterprise concepts:

- `release_artifact` -> `supply-chain:Component`
- `state_integrity_report` -> `named-graph-governance:CuratedGraph`
- `repair_plan` -> `supply-chain:MitigationAction`
- `rollback_evidence` -> `supply-chain:AlternateSource`

## Closure boundary

The mapping distinguishes:

- `inside_source`: Ontogenesis authors semantic source modules and supply-chain scenarios.
- `outside_state_runtime`: SourceOS syncd maps semantic provenance into local-first state integrity evidence.
- `boundary_membrane`: release tag, source path, graph URI, trust level, access class, retention policy, and lifecycle phase survive translation.
- `feedback_surface`: SourceOS repair, rollback, and state reports remain downstream evidence.

## Validation

Run:

```bash
make validate
```

or:

```bash
python3 tools/validate_semantic_enterprise_state_integrity.py
```

## Parent work

- `SourceOS-Linux/sourceos-syncd#17`
- `SocioProphet/delivery-excellence#21`
