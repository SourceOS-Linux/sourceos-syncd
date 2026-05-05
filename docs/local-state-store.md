# Local State Store Prototype

Status: v0.1 prototype

The local state store is the first concrete backing substrate for `sourceos-syncd` State Integrity Reports. It is intentionally small and standard-library-only.

## Purpose

The store gives the report engine something real to inspect:

- manifest state
- JSONL journal events
- explicit lane summaries
- object and tombstone counters
- producer attribution
- generation markers
- registry directories for future profile/device/actor/schema/object/index records

This moves `sourceos-syncd` from fixture-only reporting toward an actual local-first state substrate.

## Layout

```text
<store-root>/
  manifest.json
  journal.jsonl
  profiles/
  devices/
  actors/
  schemas/
  objects/
  events/
  indexes/
  checkpoints/
  repair-reports/
  tmp/
```

Directory classes:

- Durable: `profiles`, `devices`, `actors`, `schemas`, `objects`, `events`, `repair-reports`
- Rebuildable: `indexes`, `checkpoints`
- Disposable: `tmp`

Read paths must not silently initialize or reset local state. Initialization is explicit.

## CLI

Initialize a store:

```bash
sourceos-syncd store init --root /tmp/sourceos-syncd-store
```

Record events:

```bash
sourceos-syncd store record \
  --root /tmp/sourceos-syncd-store \
  --event-type add \
  --lane normal \
  --object-id obj-1 \
  --producer manual \
  --payload-json '{"path":"README.md"}'
```

Generate a store-backed State Integrity Report:

```bash
sourceos-syncd health snapshot --store-root /tmp/sourceos-syncd-store
```

Verify the resulting report:

```bash
sourceos-syncd health snapshot --store-root /tmp/sourceos-syncd-store --compact > /tmp/sourceos-syncd.snapshot.json
sourceos-syncd health verify --file /tmp/sourceos-syncd.snapshot.json --compact
```

## Reporting behavior

A store-backed report overlays live store data onto the base report:

- `stores`: active filesystem-backed store metadata
- `lanes`: lane object counts, journal bytes, replay lag, checksum state
- `pipeline`: add/update/delete accounting
- `diagnosis.local_state`: initialized state, directory classes, registry counts, manifest/journal presence
- `diagnosis.top_producers`: producer attribution from the journal

Producer attribution intentionally lives under `diagnosis` because the published report schema keeps top-level fields closed.

## Current limits

This is not yet a production sync engine. The prototype does not yet implement:

- cryptographic journal checksums
- signed checkpoints
- compaction
- purge execution
- remote replication
- policy-backed mutation authorization
- Lampstand evidence writes
- AgentPlane trust evaluation

Those are intentionally staged in the remaining integration turns.
