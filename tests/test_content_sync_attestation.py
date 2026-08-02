"""SP-GATE-001: the content-sync deploy gate must refuse.

Covers (a) the fail-closed release-attestation gate in ContentViewSyncer.plan and
(b) execute()'s abort-on-failure, so a failed verification step prevents the
nixos-rebuild switch instead of being reported after it already ran.
"""

from __future__ import annotations

from sourceos_syncd.content_sync import ContentSyncPlan, ContentViewSyncer
from sourceos_syncd.katello_client import ContentViewManifest
from sourceos_syncd.release_attestation import (
    default_attestation_verifier,
    make_release_attestation,
    verify_release_attestation,
)

ORG = "SocioProphet"
CV = "sourceos-builder-aarch64"


def manifest(version: str = "1.0") -> ContentViewManifest:
    return ContentViewManifest(
        org=ORG,
        content_view=CV,
        version=version,
        lifecycle_env="stable",
        katello_url="https://127.0.0.1:8443",
        pulp_content_url="http://127.0.0.1:8101",
        nix_cache_url="http://127.0.0.1:8101",
    )


def valid_attestation(version: str = "1.0") -> dict:
    return make_release_attestation(
        org=ORG, content_view=CV, version=version,
        signer="urn:srcos:build-pipeline:sourceos-ci",
        signature_ref="RUSxxxxxsignaturexxxxx",
    )


ALWAYS_TRUE = lambda att, key: True  # noqa: E731  (test stub verifier)
ALWAYS_FALSE = lambda att, key: False  # noqa: E731


# ── the gate refuses (fail closed) ──────────────────────────────────────────

def test_plan_blocked_without_attestation():
    syncer = ContentViewSyncer(locus="local", current_version="0.9")  # require_attestation defaults True
    plan = syncer.plan(manifest("1.0"), attestation=None)
    assert plan.policy_gate == "blocked"
    assert plan.steps == []
    assert not any("nixos-rebuild" in s for s in plan.steps)
    assert plan.epistemic_level == "Speculative"
    assert plan.attestation and plan.attestation["ok"] is False


def test_plan_blocked_attestation_for_wrong_version():
    syncer = ContentViewSyncer(locus="local", current_version="0.9",
                               attestation_public_key="RWSkey", attestation_verifier=ALWAYS_TRUE)
    # attestation binds 1.0 but Katello advertised 2.0 — must not authorize
    plan = syncer.plan(manifest("2.0"), attestation=valid_attestation("1.0"))
    assert plan.policy_gate == "blocked"
    assert "does not bind version" in plan.policy_reason


def test_plan_blocked_unsigned_attestation():
    syncer = ContentViewSyncer(locus="local", current_version="0.9", attestation_verifier=ALWAYS_TRUE)
    att = valid_attestation("1.0")
    del att["signatureRef"]  # unsigned
    plan = syncer.plan(manifest("1.0"), attestation=att)
    assert plan.policy_gate == "blocked"
    assert "missing required" in plan.policy_reason


def test_plan_blocked_when_signature_does_not_verify():
    syncer = ContentViewSyncer(locus="local", current_version="0.9",
                               attestation_public_key="RWSkey", attestation_verifier=ALWAYS_FALSE)
    plan = syncer.plan(manifest("1.0"), attestation=valid_attestation("1.0"))
    assert plan.policy_gate == "blocked"
    assert "did not verify" in plan.policy_reason


def test_plan_allowed_with_valid_attestation():
    syncer = ContentViewSyncer(locus="local", current_version="0.9",
                               attestation_public_key="RWSkey", attestation_verifier=ALWAYS_TRUE)
    plan = syncer.plan(manifest("1.0"), attestation=valid_attestation("1.0"))
    assert plan.policy_gate == "allowed"
    assert any("nixos-rebuild switch" in s for s in plan.steps)
    assert plan.epistemic_level == "Proved"
    assert plan.attestation and plan.attestation["ok"] is True


def test_receipt_carries_epistemic_level_from_attestation():
    syncer = ContentViewSyncer(locus="local", current_version="0.9",
                               attestation_public_key="RWSkey", attestation_verifier=ALWAYS_TRUE)
    plan = syncer.plan(manifest("1.0"), attestation=valid_attestation("1.0"))
    result = syncer.execute(plan, dry_run=True)
    assert result["receipt"]["epistemicLevel"] == "Proved"
    assert result["receipt"]["attestation"]["signer"].startswith("urn:srcos:build-pipeline")


# ── execute() aborts on failure: a failed step must stop the switch ─────────

def test_execute_aborts_switch_when_prior_step_fails():
    # A plan whose first step fails; the subsequent nixos-rebuild switch must NOT run.
    plan = ContentSyncPlan(
        schema="sourceos.content-sync-plan/v0.1",
        org=ORG, content_view=CV, from_version="0.9", to_version="1.0",
        lifecycle_env="stable", nix_cache_url="http://127.0.0.1:8101",
        flake_ref="github:x#y", policy_gate="allowed", policy_reason="test",
        steps=["exit 1", "nixos-rebuild switch --flake 'github:x#y'"],
        epistemic_level="Proved",
    )
    syncer = ContentViewSyncer(locus="local")
    result = syncer.execute(plan, dry_run=False)
    statuses = {r["step"]: r["status"] for r in result["results"]}
    assert statuses["exit 1"] == "failed"
    assert statuses["nixos-rebuild switch --flake 'github:x#y'"] == "not-run"
    assert result["status"] == "failed"


# ── the default verifier is fail-closed ─────────────────────────────────────

def test_default_verifier_fails_closed_without_key():
    assert default_attestation_verifier(valid_attestation("1.0"), None) is False


def test_default_verifier_fails_closed_without_signature():
    att = valid_attestation("1.0")
    del att["signatureRef"]
    assert default_attestation_verifier(att, "RWSkey") is False


def test_verify_decision_absent_is_speculative():
    d = verify_release_attestation(None, org=ORG, content_view=CV, version="1.0",
                                   trusted_key="RWSkey", verifier=ALWAYS_TRUE)
    assert d.ok is False
    assert d.epistemic_level == "Speculative"
