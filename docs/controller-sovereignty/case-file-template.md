# Controller Case File Template

Use this template for redacted controller-sovereignty evidence. Repository artifacts should contain summaries, not private device records.

## Summary

- Case ID: `<case-id>`
- Date range: `<start> to <end>`
- Machine class: `<redacted>`
- OS family/build: `<OS family and build>`
- Primary finding: `<one sentence>`

## Controller

- Controller name: `<Spotlight / Photos / APFS / CoreWiFi / Network Extension / updater / other>`
- Owner: `<first-party | third-party | user | unknown>`
- Representative services:
  - `<service name>`
- Resource coalition: `<if known>`

## Trigger model

- Foreground user action observed: `<yes | no | unknown>`
- Background scheduler observed: `<yes | no | unknown>`
- Network trigger observed: `<yes | no | unknown>`
- Filesystem trigger observed: `<yes | no | unknown>`
- Cloud/sync trigger observed: `<yes | no | unknown>`

## Observed behavior

Describe what the controller did in plain language.

Example:

> Metadata controller compacted index payloads and dirtied several GB of file-backed memory while running non-frontmost background work.

## Resource impact

- CPU: `<duration / average / peak if available>`
- Disk writes: `<MB/GB and duration if available>`
- Memory: `<RSS/footprint if available>`
- Network: `<interfaces, tunnels, or traffic-class evidence if available>`
- Power state: `<AC / battery / idle / active>`
- Platform action: `<none / managed / unknown>`

## Evidence summary

| Evidence | Sanitized value |
|---|---|
| Event type | `<disk writes / cpu usage / telemetry loop / network policy / other>` |
| Command | `<process name>` |
| Time window | `<redacted or normalized>` |
| Stack family | `<Spotlight compaction / Photos database rewrite / APFS traversal / Wi-Fi telemetry>` |
| User activity | `<active / idle / unknown>` |
| Power source | `<AC / battery / unknown>` |

## User-control gap

- Was the behavior visible in the UI?
- Could the user defer it?
- Could the user budget it?
- Could the user audit what file class, interface, or service was touched?
- Could the user revise the capability safely?

## Classification

- Evidence confidence: `<low / medium / high>`
- Resource impact: `<low / medium / high>`
- User-control gap: `<low / medium / high>`
- Recommended design response: `<observe / budget / governed profile / redesign>`

## SourceOS design requirement

Translate the case into a requirement.

Example:

> A metadata indexer that exceeds a configured write budget must emit a ControllerBudgetExceeded event with file-class attribution and user-visible policy state.
