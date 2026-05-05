# SourceOS Control Plane Integration

Status: v0.1 implementation spine

This spec turns the Apple/macOS forensic review into SourceOS integration work. It does not copy Apple private implementation. It extracts the operating-system lessons: strong service supervision, capability-gated authority, wake/power receipts, typed incident bundles, hermetic app launch, parser isolation, and product identity invariants.

## Core doctrine

Every event must have:

- actor
- authority domain
- declared capability
- policy decision
- causal parent
- resource cost
- privacy class
- retention class
- human-readable remediation

Raw logs are evidence. The product surface is a typed, coalesced, causally linked event with an operator narrative.

## Integration spine

The first integration target is the schema package in `schemas/` plus the golden fixtures in `examples/`.

These contracts are intentionally product-neutral. `sourceos-syncd`, BearBrowser, TurtleTerm, PolicyFabric, AgentPlane, SocioSphere, Lampstand, memory-mesh, smart-tree, and DeliveryExcellence should all consume the same shapes instead of inventing local event formats.

## Apple-derived requirements

### Capability denials

Expected denials are not errors. They must be represented as `notice` + `blocked_expected`, with the policy rule and explanation code preserved.

### Wake receipts

Sleep is not off. Any network, maintenance, sync, update, indexing, or security activity during sleep must produce a wake receipt containing the beneficiary service, trigger, duration, power class, and policy decision.

### Product identity

User-facing product identity must be invariant across bundle, dock, menu, process, helper, profile, crash, update, and event surfaces. Upstream provenance belongs in About/license surfaces, not product identity.

### Hermetic launch

Packaged apps must not inherit polluted shell environments. Launch manifests declare executable path, PATH, allowed variables, denied variables, helper prefixes, and identity invariants.

### Incident bundles

An incident bundle is a signed local-first artifact. It should be redacted by default, export-controlled, and able to reconstruct the causal graph without dumping raw logs into the operator surface.

### Parser isolation

Indexers, media decoders, browser renderers, QuickLook-style previewers, document parsers, and AI content processors must run as constrained workers with content-type boundaries and resource budgets.

## Release gates

A SourceOS service or product is not release-ready unless:

1. It has a service manifest.
2. It emits canonical events or explicitly documents why it does not.
3. It declares required, optional, and denied capabilities.
4. It has a hermetic launch manifest if it is an app.
5. It produces an incident bundle for crashes, denial storms, wake anomalies, identity mismatches, and parser faults.
6. It does not perform silent remote trust lookup.
7. It does not emit remote telemetry by default.
8. It coalesces repeated expected denials.
9. It preserves privacy while retaining causal structure.
10. It has a DeliveryExcellence signal-quality metric.

## First implementation target

The immediate implementation unit is schema validation and fixture validation:

```bash
python3 tools/validate_control_plane_examples.py
```

That script intentionally uses only Python standard library checks. It is not a full JSON Schema validator. Its purpose is to catch broken examples and enforce controlled vocabulary alignment in minimal environments.
