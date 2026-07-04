# Controller Sovereignty Toolkit

This directory defines the SourceOS controller-sovereignty lane for `sourceos-syncd`.

The motivating observation is that modern machines are governed by autonomous controllers rather than by a simple process list. A controller is any actor that can consume material resources or mutate user/system state without a direct foreground user command.

Examples include metadata indexing, media analysis, cloud sync, filesystem maintenance, network policy, wireless telemetry, software update, and third-party application updaters.

The SourceOS standard is:

> No hidden autonomous controller may consume material resources without registration, budget, logging, and revocation.

## Contents

- `case-file-template.md` — sanitized evidence template for controller incidents.
- `controller-registry.schema.yaml` — draft controller registry schema.
- `sovereignty-dashboard.md` — first dashboard/product model.

## Non-goals

This lane does not store raw private diagnostic logs, device identifiers, account identifiers, serial numbers, local IPs, Wi-Fi identifiers, packet payloads, or personal file paths. Evidence should be summarized and redacted before it becomes a repository artifact.

## Relationship to sourceos-syncd

`sourceos-syncd` is the state integrity daemon. Controller sovereignty extends that mission from replicated state to operating-system behavior: state changes must be observable, attributable, budgeted, repairable, and explainable before automation is allowed to act.
