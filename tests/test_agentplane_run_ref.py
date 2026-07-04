from __future__ import annotations

from sourceos_syncd.cli import build_parser
from sourceos_syncd.content_sync import ContentViewSyncer, ContentSyncPlan, SYNC_SCHEMA


def _make_plan(**kwargs) -> ContentSyncPlan:
    defaults = dict(
        schema=SYNC_SCHEMA,
        org="SocioProphet",
        content_view="sourceos-builder-aarch64",
        from_version="1.0",
        to_version="1.1",
        lifecycle_env="stable",
        nix_cache_url="http://127.0.0.1:8101",
        flake_ref="github:SociOS-Linux/source-os#builder-aarch64",
        policy_gate="allowed",
        policy_reason="test",
        steps=["nix copy", "nixos-rebuild"],
    )
    defaults.update(kwargs)
    return ContentSyncPlan(**defaults)


def test_receipt_includes_agentplane_run_ref_when_set() -> None:
    syncer = ContentViewSyncer(agentplane_run_ref="urn:agentplane:run:abc123")
    plan = _make_plan()
    receipt = syncer._build_receipt(
        cycle_id="cycle-1",
        plan=plan,
        outcome="dry_run",
        steps=[],
        duration_ms=0,
    )
    assert receipt["agentplaneRunRef"] == "urn:agentplane:run:abc123"


def test_receipt_agentplane_run_ref_is_none_by_default() -> None:
    syncer = ContentViewSyncer()
    plan = _make_plan()
    receipt = syncer._build_receipt(
        cycle_id="cycle-2",
        plan=plan,
        outcome="dry_run",
        steps=[],
        duration_ms=0,
    )
    assert receipt["agentplaneRunRef"] is None


def test_cli_sync_apply_accepts_agentplane_run_ref_flag() -> None:
    parser = build_parser()
    args = parser.parse_args([
        "sync", "apply",
        "--katello-password", "pw",
        "--agentplane-run-ref", "urn:agentplane:run:xyz",
        "--compact",
    ])
    assert args.agentplane_run_ref == "urn:agentplane:run:xyz"


def test_cli_sync_apply_agentplane_run_ref_defaults_none() -> None:
    parser = build_parser()
    args = parser.parse_args(["sync", "apply", "--katello-password", "pw"])
    assert args.agentplane_run_ref is None


def test_cli_sync_daemon_accepts_agentplane_run_ref_flag() -> None:
    parser = build_parser()
    args = parser.parse_args([
        "sync", "daemon",
        "--katello-password", "pw",
        "--agentplane-run-ref", "urn:agentplane:run:daemon-ref",
    ])
    assert args.agentplane_run_ref == "urn:agentplane:run:daemon-ref"
