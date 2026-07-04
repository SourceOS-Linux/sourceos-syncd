"""Tests for KatelloContentClient and ContentViewSyncer."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from sourceos_syncd.content_sync import ContentSyncPlan, ContentViewSyncer
from sourceos_syncd.katello_client import (
    ContentViewManifest,
    KatelloClientError,
    KatelloContentClient,
)


# ── ContentViewManifest ────────────────────────────────────────────────────

def make_manifest(**kwargs) -> ContentViewManifest:
    defaults = dict(
        org="SocioProphet",
        content_view="sourceos-builder-aarch64",
        version="1.0",
        lifecycle_env="dev",
        katello_url="https://127.0.0.1:8443",
        pulp_content_url="http://127.0.0.1:8101",
        nix_cache_url="http://127.0.0.1:8101/socioprophet/content/sourceos/nix-cache-aarch64-linux/",
    )
    defaults.update(kwargs)
    return ContentViewManifest(**defaults)


def test_manifest_to_dict():
    m = make_manifest()
    d = m.to_dict()
    assert d["org"] == "SocioProphet"
    assert d["content_view"] == "sourceos-builder-aarch64"
    assert d["version"] == "1.0"
    assert d["lifecycle_env"] == "dev"
    assert "nix_cache_url" in d


# ── ContentViewSyncer.plan ─────────────────────────────────────────────────

def test_plan_allowed_new_version():
    syncer = ContentViewSyncer(locus="local", current_version="0.9")
    plan = syncer.plan(make_manifest(version="1.0"))
    assert plan.policy_gate == "allowed"
    assert plan.allowed
    assert any("nix copy" in s for s in plan.steps)
    assert any("nixos-rebuild" in s for s in plan.steps)
    # no signing steps when key not configured
    assert not any("minisign" in s for s in plan.steps)


def test_plan_with_signing_key_prepends_verify_steps():
    pub_key = "RWSxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    syncer = ContentViewSyncer(locus="local", current_version="0.9", signing_public_key=pub_key)
    plan = syncer.plan(make_manifest(version="1.0"))
    assert plan.allowed
    step_cmds = " ".join(plan.steps)
    assert "minisign" in step_cmds
    assert "nix-cache-info" in step_cmds
    # verify step must come before nix copy
    minisign_idx = next(i for i, s in enumerate(plan.steps) if "minisign" in s)
    nix_copy_idx = next(i for i, s in enumerate(plan.steps) if "nix copy" in s)
    assert minisign_idx < nix_copy_idx


def test_plan_with_signing_key_embeds_public_key():
    pub_key = "RWSxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    syncer = ContentViewSyncer(locus="local", signing_public_key=pub_key)
    plan = syncer.plan(make_manifest(version="1.0"))
    assert any(pub_key in s for s in plan.steps)


def test_plan_noop_same_version():
    syncer = ContentViewSyncer(locus="local", current_version="1.0")
    plan = syncer.plan(make_manifest(version="1.0"))
    assert plan.policy_gate == "no-op"
    assert plan.steps == []


def test_plan_denied_invalid_locus():
    syncer = ContentViewSyncer(locus="burst_cloud")
    plan = syncer.plan(make_manifest())
    assert plan.policy_gate == "denied"
    assert not plan.allowed
    assert "burst_cloud" in plan.policy_reason


def test_plan_allowed_trusted_private():
    syncer = ContentViewSyncer(locus="trusted_private", current_version=None)
    plan = syncer.plan(make_manifest(version="2.0"))
    assert plan.policy_gate == "allowed"


def test_plan_no_current_version_always_syncs():
    syncer = ContentViewSyncer(locus="local", current_version=None)
    plan = syncer.plan(make_manifest(version="1.0"))
    assert plan.policy_gate == "allowed"
    assert len(plan.steps) == 2


def test_plan_to_dict_roundtrip():
    syncer = ContentViewSyncer(locus="local")
    plan = syncer.plan(make_manifest(version="1.0"))
    d = plan.to_dict()
    assert d["schema"].startswith("sourceos.content-sync-plan")
    assert d["policy_gate"] in ("allowed", "denied", "no-op")
    assert isinstance(d["steps"], list)


# ── ContentViewSyncer.execute dry-run ─────────────────────────────────────

def test_execute_dry_run_allowed():
    syncer = ContentViewSyncer(locus="local")
    plan = syncer.plan(make_manifest(version="1.0"))
    result = syncer.execute(plan, dry_run=True)
    assert result["status"] == "dry_run"
    for r in result["results"]:
        assert r["status"] == "dry_run"


def test_execute_dry_run_denied():
    syncer = ContentViewSyncer(locus="burst_cloud")
    plan = syncer.plan(make_manifest(version="1.0"))
    result = syncer.execute(plan, dry_run=True)
    assert result["status"] == "denied"
    assert "policy_gate" in result
    assert "receipt" in result
    assert result["receipt"]["outcome"] == "denied"


def test_execute_dry_run_noop():
    syncer = ContentViewSyncer(locus="local", current_version="1.0")
    plan = syncer.plan(make_manifest(version="1.0"))
    result = syncer.execute(plan, dry_run=True)
    assert result["status"] == "skipped"


# ── KatelloContentClient URL construction ─────────────────────────────────

def test_nix_cache_url_from_https_port():
    """Pulp content URL derived from Foreman HTTPS URL by port replacement."""
    with patch.object(KatelloContentClient, "_get") as mock_get:
        mock_get.side_effect = [
            {"results": [{"id": 1}]},  # get_org_id
            {"results": [{"id": 2}]},  # get_content_view_id
            {"results": [{"id": 3}]},  # get_lifecycle_env_id
            {"results": [{"id": 10, "version": "1.0", "description": "test"}]},  # versions
        ]
        client = KatelloContentClient(
            base_url="https://127.0.0.1:8443",
            username="admin",
            password="secret",
            verify_ssl=False,
        )
        manifest = client.get_latest_version("sourceos-builder-aarch64", "dev")
    assert "8101" in manifest.nix_cache_url
    assert manifest.version == "1.0"
    assert manifest.org == "SocioProphet"


def test_get_latest_version_raises_on_empty_results():
    with patch.object(KatelloContentClient, "_get") as mock_get:
        mock_get.return_value = {"results": [{"id": 1}]}
        client = KatelloContentClient(
            "https://127.0.0.1:8443", "admin", "x", verify_ssl=False
        )
        mock_get.side_effect = [
            {"results": [{"id": 1}]},  # org
            {"results": [{"id": 2}]},  # cv
            {"results": [{"id": 3}]},  # env
            {"results": []},           # versions — empty
        ]
        with pytest.raises(KatelloClientError, match="No version"):
            client.get_latest_version("sourceos-builder-aarch64", "dev")


def test_get_org_raises_when_not_found():
    with patch.object(KatelloContentClient, "_get", return_value={"results": []}):
        client = KatelloContentClient(
            "https://127.0.0.1:8443", "admin", "x", verify_ssl=False
        )
        with pytest.raises(KatelloClientError, match="Organization not found"):
            client.get_org_id()
