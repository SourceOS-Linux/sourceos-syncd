# Policy Observation Examples

These fixtures exercise the registry-backed policy decision normalizer.

## Registry

The explanation-code registry lives at:

- `policy/explanation-codes.v0.1.json`

The registry schema lives at:

- `schemas/sourceos.policy-explanation-registry.v0.1.schema.json`

## Observation schema

Raw normalized observations use:

- `schemas/sourceos.policy-observation.v0.1.schema.json`

The observation is not the final operator product. It is the input that the normalizer converts into a canonical `policy.decision` event.

## Valid observations

- `expected-metadata-boundary.json`: expected file-data block against executable/package metadata boundary.
- `expected-network-disabled.json`: expected network/trust lookup block under local-first policy.
- `degraded-trust-local-only.json`: degraded trust path where remote/enriched evidence is unavailable or disallowed.
- `attack-like-privilege-boundary-probe.json`: critical privilege-boundary probe blocked by policy.

## Invalid observations

- `invalid/expected-boundary-as-attack-like.json`: attempts to use `POLICY_EXPECTED_METADATA_BOUNDARY` while overriding the semantic outcome to `blocked_attack_like`, severity to `critical`, and risk to `critical`. This must fail because it contradicts the registry.

## Validation contract

```bash
python3 tools/sourceos_policy_normalizer.py validate-registry
python3 tools/sourceos_policy_normalizer.py validate-observation examples/policy-observations/expected-metadata-boundary.json
python3 tools/sourceos_policy_normalizer.py normalize examples/policy-observations/expected-metadata-boundary.json
! python3 tools/sourceos_policy_normalizer.py validate-observation examples/policy-observations/invalid/expected-boundary-as-attack-like.json
```

The Makefile exposes this as:

```bash
make validate-policy-normalizer
```

The full validation contract includes it through:

```bash
make validate
```

## Design intent

The normalizer prevents semantic laundering:

- expected denials cannot be inflated into fake critical incidents;
- attack-like probes cannot be downgraded into harmless notices;
- degraded trust remains explicit instead of becoming ambiguous failure noise;
- network-disabled local-first behavior is treated as a controlled safety state, not a connectivity error.
