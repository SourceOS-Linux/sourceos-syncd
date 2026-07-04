# Sovereignty Dashboard Model

The dashboard presents a machine by controller class rather than by raw process. It should answer four questions:

1. Who is acting?
2. What authority do they have?
3. What resource budget did they consume?
4. What can the user inspect, defer, budget, or revise?

## Controller cards

### Network

Shows:

- physical interfaces
- peer wireless interfaces
- tunnel interfaces
- proxy state
- Network Extension state
- per-process socket summary
- observed traffic classes
- low-power network presence

### Spotlight / Metadata

Shows:

- indexed volumes
- active metadata workers
- recent write and CPU events
- high-churn paths
- excluded paths
- budget status

### Photos / Media

Shows:

- media library services
- photo/media analysis services
- cloud photo services
- recent database/write events
- cloud sync state
- analysis workloads

### Filesystem

Shows:

- filesystem traversal events
- APFS service state
- metadata maintenance
- recent CPU reports

### Updates

Shows:

- platform update services
- application updater services
- recent update write events
- pending update state
- maintenance-window status

### Security / Policy Extensions

Shows:

- system extensions
- Network Extensions
- EndpointSecurity clients
- firewall/filter state
- trust and attestation status

## Minimum viable terminal view

| Controller | State | Last event | Impact | User action |
|---|---|---|---|---|
| Spotlight / Metadata | Active | disk writes | budget exceeded | inspect / budget |
| Photos / Media | Idle | database rewrite | high | quarantine profile |
| Filesystem | Idle | CPU usage | medium | schedule |
| Wireless | Active | telemetry loop | persistent | policy view |
| Application Updater | Idle | disk writes | medium | maintenance window |
| Network Policy | Active | extension authority | unknown | inspect |

## Required SourceOS events

- `ControllerRegistered`
- `ControllerCapabilityDeclared`
- `ControllerBudgetExceeded`
- `ControllerTouchedFileClass`
- `ControllerOpenedNetworkSurface`
- `ControllerEnteredIdleWork`
- `ControllerExitedIdleWork`
- `ControllerPolicyChanged`

## Product rule

If a controller can act without a foreground user command, it must have a visible registry entry, a declared resource budget, and a human-readable audit trail.
