# SourceOS Estate Rollout Guide

**Scope:** Deploying `sourceos-syncd` across a fleet of managed workstations  
**Implements:** sourceos-syncd#2

---

## Overview

`sourceos-syncd` is deployed as a systemd service on each managed device.  
It owns the local State Integrity lane, syncs content views via Katello/Foreman, and surfaces operator narratives to the SocioSphere dashboard.

The rollout follows a three-phase model: canary → ring-A → ring-B/full estate.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| NixOS ≥ 24.05 (aarch64 or x86_64) | Tested on Asahi and standard x86 |
| Katello/Foreman reachable at `$KATELLO_URL` | HTTPS, self-signed cert supported via `--no-verify-ssl` for dev |
| `sourceos-syncd` v0.3.x RPM in the content view | Built by the `sourceos-builder-aarch64` view |
| `KATELLO_PASSWORD_FILE` set or `KATELLO_PASSWORD` env | Password at rest in a secret store, not in the unit file |
| `sourceos-syncd status --store-root /var/lib/sourceos-syncd` exits 0 | Pre-check before promotion |

---

## Step 1 — Prepare the content view

```bash
# Plan what will be applied
sourceos-syncd sync plan \
  --katello-url "$KATELLO_URL" \
  --org SocioProphet \
  --content-view sourceos-builder-aarch64 \
  --lifecycle-env candidate
```

Review the output. `policy_gate` must be `"allowed"` before proceeding.  
Gate on the signing key if you have one:

```bash
sourceos-syncd sync plan \
  --signing-public-key "RWS..." \
  ... 
```

---

## Step 2 — Deploy to canary (1–3 devices)

Choose canary hosts. On each:

```bash
# Dry-run first (no changes)
sourceos-syncd sync apply \
  --katello-url "$KATELLO_URL" \
  --org SocioProphet \
  --content-view sourceos-builder-aarch64 \
  --lifecycle-env candidate \
  --store-root /var/lib/sourceos-syncd

# Promote when dry-run looks good
sourceos-syncd sync apply --execute \
  --katello-url "$KATELLO_URL" \
  --org SocioProphet \
  --content-view sourceos-builder-aarch64 \
  --lifecycle-env candidate \
  --store-root /var/lib/sourceos-syncd
```

Enable and start the daemon:

```bash
systemctl enable --now sourceos-syncd
```

Verify the canary:

```bash
sourceos-syncd sync check-health --store-root /var/lib/sourceos-syncd
sourceos-syncd sync status --store-root /var/lib/sourceos-syncd
sourceos-syncd health snapshot
```

All three must return exit 0 before ring-A promotion.

---

## Step 3 — Ring-A rollout (10–20% of estate)

Promote the content view to the `stable` lifecycle env:

```bash
sourceos-syncd sync plan \
  --lifecycle-env stable \
  ...
```

Roll out to ring-A hosts using your configuration management tool (Ansible, Puppet, NixOS colmena).  
The daemon can also be driven purely from environment variables for automation:

```bash
KATELLO_URL=https://katello.internal:8443 \
KATELLO_USER=admin \
KATELLO_PASSWORD_FILE=/run/secrets/katello-password \
KATELLO_ORG=SocioProphet \
KATELLO_CONTENT_VIEW=sourceos-builder-aarch64 \
KATELLO_LIFECYCLE_ENV=stable \
sourceos-syncd sync daemon --from-env
```

Monitor ring-A health:

```bash
# On each host
sourceos-syncd sync status
sourceos-syncd authority report
sourceos-syncd coherence status
```

Check that `allRequiredReachable` is `true` in the authority report before full rollout.

---

## Step 4 — Full estate rollout

Once ring-A is stable for ≥ 24 hours with no repair-required events:

1. Promote the content view to `production` (your final lifecycle env).
2. Roll out to remaining hosts in ring-B using the same pattern.
3. After rollout, run the noise budget check:

```bash
sourceos-syncd noise-budget status
```

`budgetUtilization` above 0.5 indicates event churn worth investigating before considering the rollout complete.

---

## Monitoring and operator cards

The SocioSphere dashboard consumes operator narrative cards from the `/narrativez` endpoint:

```
GET http://127.0.0.1:8765/narrativez
```

For estate-level aggregation, a collector scrapes each device's `/narrativez` and `/authorityz` endpoints. The coherence plane snapshot is available at `/coherencez`.

Prometheus metrics are at `/metrics` (Prometheus text format). The key gauges:

| Metric | Meaning |
|---|---|
| `sourceos_syncd_ready` | 1 when ready, 0 otherwise |
| `sourceos_syncd_initialized` | 1 when local store is initialized |
| `sourceos_syncd_corrupted_objects` | Count of corrupted store objects |
| `sourceos_syncd_replay_lag_events` | Journal replay lag |

---

## Rollback

If a host fails health checks after the apply:

```bash
# Show the last receipt and its outcome
sourceos-syncd receipts last --store-root /var/lib/sourceos-syncd

# Re-apply the previous version
sourceos-syncd sync apply --execute \
  --current-version <previous-version> \
  --lifecycle-env stable \
  ...
```

The daemon tolerates network blips and will retry on the next poll cycle (default 300 s).

---

## Security notes

- The daemon binds only to `127.0.0.1:8765`; the HTTP service is local-only.
- All harvest envelopes produced by `sourceos-syncd harvest wrap` have `sensitive_data_excluded: true` set unconditionally. Raw prompts, credentials, and session tokens are never included in harvest payloads.
- The Katello password must come from `KATELLO_PASSWORD_FILE` or `KATELLO_PASSWORD`. Never pass it as a CLI argument in production (it appears in `ps` output).

---

## Troubleshooting

| Symptom | Check |
|---|---|
| `sourceos_syncd_ready 0` in Prometheus | `sourceos-syncd health explain` — look at `diagnosis.status` |
| Daemon not starting | `journalctl -u sourceos-syncd -n 50` |
| `katello_reachable: false` in check-health | Network / TLS cert issue; `--no-verify-ssl` for dev only |
| `allRequiredReachable: false` in authority report | Identity or policy authority is offline; expected at first boot until identity is confirmed |
| High `budgetUtilization` | `sourceos-syncd noise-budget status` then flush: `sourceos-syncd noise-budget flush` |
