# Controller Operator Profiles

Operator profiles define what autonomous controllers may do under a given machine posture.

The profile is not a convenience setting. It is a sovereignty boundary: it determines whether background controllers may consume resources, touch local state, use network surfaces, or run while idle.

## Profile matrix

| Capability | Workstation | Investigation | Personal | Maintenance |
|---|---:|---:|---:|---:|
| Metadata indexing | budgeted | restricted | allowed | allowed |
| Media analysis | restricted | blocked by default | allowed | allowed |
| Cloud photo sync | explicit | blocked by default | allowed | allowed |
| Filesystem traversal | budgeted | observed only | budgeted | allowed |
| Peer wireless | explicit | blocked by default | allowed | explicit |
| Network tunnels | explicit | explicit | allowed | explicit |
| Application updaters | maintenance window | blocked by default | allowed | allowed |
| Platform update | explicit | explicit | allowed | allowed |
| Low-power network presence | explicit | blocked by default | allowed | explicit |
| Private cloud compute | explicit | blocked by default | allowed | explicit |

## Workstation profile

Goal: stable development and daily work.

Defaults:

- Indexing is allowed only under budget.
- Generated directories and high-churn build outputs should be excluded from indexing.
- Media analysis is restricted.
- Cloud sync is allowed only for declared paths or services.
- Peer wireless is explicit rather than ambient.
- Update work is scheduled into a maintenance window.

Required events:

- `ControllerBudgetObserved`
- `ControllerBudgetExceeded`
- `ControllerEnteredIdleWork`
- `ControllerExitedIdleWork`

## Investigation profile

Goal: evidence preservation and minimal ambient mutation.

Defaults:

- Cloud/media analysis is blocked by default.
- Metadata indexing is restricted or paused unless explicitly allowed.
- Peer wireless and low-power network presence are blocked by default.
- Network extensions and tunnels must be visible.
- Raw outputs remain local and are summarized before they enter a repository.

Required events:

- `ControllerOpenedNetworkSurface`
- `ControllerTouchedResourceClass`
- `ControllerPolicyChanged`

## Personal profile

Goal: ordinary convenience with budget visibility.

Defaults:

- Cloud sync is allowed.
- Media analysis is allowed.
- Metadata indexing is allowed.
- Background work is still budgeted and visible.
- Budget excess produces user-visible explanation.

Required events:

- `ControllerBudgetObserved`
- `ControllerBudgetExceeded`

## Maintenance profile

Goal: deliberate system maintenance.

Defaults:

- Updates may run.
- Index rebuilds may run.
- Filesystem maintenance may run.
- Cloud repair jobs may run only if explicitly selected.
- Profile has a start and end time.

Required events:

- `ControllerPolicyChanged`
- `ControllerEnteredIdleWork`
- `ControllerExitedIdleWork`

## Profile transition rule

A profile transition must be explicit, durable, and auditable. SourceOS must record:

- previous profile
- new profile
- actor that changed it
- reason
- timestamp
- controllers whose effective capabilities changed

## Product requirement

A user should be able to answer this question at any moment:

> Which profile is active, which controllers gained authority from it, and what budget remains?
