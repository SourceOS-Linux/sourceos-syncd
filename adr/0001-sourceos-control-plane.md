# ADR 0001: SourceOS Control Plane as the Integration Spine

Status: Accepted

## Context

The Apple/macOS forensic review showed a mature hidden control plane: service supervision, XPC lifecycle, entitlement boundaries, wake management, code-signing state, memory-pressure cleanup, incident reports, parser workers, and cloud/security/telemetry daemons.

The failure mode is not lack of machinery. The failure mode is owner opacity, noisy logs, weak causal explanation, product identity leakage, and unclear policy boundaries.

SourceOS needs comparable engineering primitives with a better operating model: local-first, inspectable, policy-governed, explainable, and suitable for agents.

## Decision

`sourceos-syncd` will host the first canonical control-plane contracts:

- canonical event schema
- service manifest schema
- capability schema
- launch manifest schema
- incident bundle schema
- golden examples
- validation tooling

Adjacent repos must integrate by consuming these contracts rather than creating incompatible local formats.

## Consequences

Positive:

- SourceOS gets one language for events, services, capabilities, launch, and incidents.
- Products like BearBrowser and TurtleTerm can be audited consistently.
- PolicyFabric, AgentPlane, SocioSphere, Lampstand, and DeliveryExcellence get stable integration points.
- Expected denials and noise storms become product-grade events instead of raw log noise.

Tradeoffs:

- Early work is schema-heavy before daemon implementation.
- Repos must align vocabulary and release gates.
- Product teams must treat identity, launch, telemetry, and helper topology as release-blocking concerns.

## Non-goals

- Reimplementing Apple launchd, APFS, XPC, or private entitlement systems.
- Building a production daemon before the contracts are stable.
- Treating raw logs as the operator-facing product.
