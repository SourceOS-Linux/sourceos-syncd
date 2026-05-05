# SourceOS State Integrity Contracts

Canonical architecture: `SourceOS-Linux/sourceos-spec/docs/architecture/sourceos-state-integrity-layer.md`

This repository implements the daemon and CLI contracts for SourceOS State Integrity. The first cut is intentionally contract-first: downstream repos can integrate against stable response shapes before persistence, transports, and repair engines are complete.

## Contract Principles

- Structured JSON is the stable integration boundary.
- Logs are not API contracts.
- Destructive operations must have dry-run and explicit target scope.
- Durable state, rebuildable state, and disposable state must be classified separately.
- Policy denials, conflicts, transport failures, and repair-needed states must not collapse into generic errors.
- Agent writes must be attributable to registered actors.

## Current CLI Commands

```bash
sourceos-syncd status --json
sourceos-syncd doctor --json
sourceos-syncd explain <object> --json
sourceos-syncd plans --json
sourceos-syncd actors --json
sourceos-syncd schemas --json
sourceos-syncd conflicts --json
sourceos-syncd repair --dry-run --json
sourceos-syncd repair --apply --json
sourceos-syncd profiles --json
sourceos-syncd devices --json
sourceos-syncd export <workspace|profile|object> --json
sourceos-syncd import <bundle> --json
```

## Expected Wrapper

`sourceos-devtools` should expose these as:

```bash
sourceos sync status
sourceos sync doctor
sourceos sync explain <object>
sourceos sync plans
sourceos sync actors
sourceos sync schemas
sourceos sync conflicts
sourceos sync repair --dry-run
sourceos sync repair --apply
sourceos sync profiles
sourceos sync devices
sourceos sync export <workspace|profile|object>
sourceos sync import <bundle>
```

## Model Families

The initial Rust models define:

- health states
- durability classes
- actor records
- source objects
- schema contracts
- sync plans
- conflicts
- policy decisions
- integrity events
- state status
- repair reports

## MVP Persistence Boundary

The next implementation phase should add persistence in this order:

1. local config/profile/device discovery
2. local append-only event log
3. actor registry
4. schema registry
5. object registry
6. derived index classification
7. dry-run repair of a derived index
8. policy decision adapter
9. workspace/file object adapter
10. agent transaction path

## Non-Goals for First Cut

- no cloud replication
- no hidden repair
- no destructive import/export
- no anonymous agent writes
- no log-scraping integrations
- no silent schema drift
