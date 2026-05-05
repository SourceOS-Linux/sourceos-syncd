# MVP Roadmap

The first `sourceos-syncd` milestone must prove SourceOS State Integrity, not full cloud-drive parity.

## Milestone 0: Contract Seed

Status: in progress

- Rust crate
- stable JSON CLI stubs
- model contracts
- repair report contract
- contract docs
- CI

## Milestone 1: Local State Foundations

- determine state directory layout
- write config loader
- create local append-only event log
- create actor registry persistence
- create schema registry persistence
- create object registry persistence
- add deterministic ids where appropriate
- add tests for serialization compatibility

## Milestone 2: Doctor and Repair

- classify durable, rebuildable, and disposable state
- detect missing/corrupt derived index
- produce dry-run repair report
- rebuild derived index from event log
- write applied repair report
- never mutate durable state during derived-state repair

## Milestone 3: Policy Hook

- define policy decision adapter trait
- add allow/deny/review-required mock adapter
- require policy decision references on export, repair-apply, schema migration, delete, and replication plans
- emit structured policy denial events

## Milestone 4: Workspace/File Adapter

- model workspace object
- model file object metadata
- track basic create/update/delete events
- classify content hash and provenance
- expose `explain <object>` from registry state

## Milestone 5: Agent Transaction Path

- register agent actor
- represent draft/proposed/applied/reverted object transactions
- attribute changes to actor/profile/workspace
- block anonymous durable writes

## Milestone 6: Surfaces

- `sourceos-devtools` wrapper
- `sourceos-shell` context
- TurtleTerm status surface
- SourceOS Workspace health card
- Agent-Term ChatOps flow
- Sherlock event indexing
- Holmes reasoning examples
- Lampstand visualization plan

## Stop Condition for First Stable Cut

The MVP is stable when it can answer from structured local state:

- What is this object?
- Which schema governs it?
- Who or what last changed it?
- Which device and profile own it?
- Is it safe to sync or export?
- Why is it blocked?
- What conflicts exist?
- What can be repaired automatically?
- What requires human review?
- What data is durable vs rebuildable?
