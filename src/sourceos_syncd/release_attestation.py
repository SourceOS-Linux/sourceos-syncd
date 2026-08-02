"""Release attestation for the content-sync deploy gate (SP-GATE-001).

The failure this closes: sourceos-syncd would plan a `nixos-rebuild switch` for
any newer content-view version a (possibly unauthenticated) Katello advertised.
The only signature check was over nix-cache-info — cache *transport*, not the
promotion *decision*. So possession of the promote credential was, in effect,
runtime authority over every enrolled device.

This module binds the switch to a signed attestation of the specific version,
and — the whole point — FAILS CLOSED:

  * absence of an attestation returns Speculative, not Proved;
  * an attestation for a different artifact/version does not authorize this one
    (possession of *an* attestation is not authorization for *this* switch);
  * if the verifier cannot run (no key, no minisign), the answer is refuse, not
    assume-valid — a gate that cannot fail is not a gate.

The attestation record follows the sourceos-spec `SignedArtifact` shape
(artifactId, signer, algorithm, timestamp, issuer?, signatureRef). The cryptographic
step is injectable so tests are deterministic; the default performs a real
minisign verification and returns False on any failure or missing dependency.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ATTESTATION_SCHEMA = "sourceos.release-attestation/v0.1"

# The fields a usable SignedArtifact release attestation must carry. signatureRef
# is required here (a SignedArtifact with no signature is not evidence of signing).
REQUIRED_FIELDS = ("artifactId", "signer", "algorithm", "timestamp", "signatureRef")

Verifier = Callable[[dict[str, Any], "str | None"], bool]


def utc_now() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def expected_artifact_id(org: str, content_view: str, version: str) -> str:
    """The artifactId an attestation MUST carry to authorize this exact version.

    Binding on (org, content_view, version) is what makes an attestation for
    v1.2 unusable to legalize a switch to v1.3 — the anti-retroactive-legalization
    property the sourceos-boot digest pin has, applied to promotion.
    """
    return f"urn:srcos:content-view:{org}:{content_view}:{version}"


@dataclass(frozen=True)
class AttestationDecision:
    ok: bool
    reason: str
    epistemic_level: str  # "Proved" when ok, "Speculative" when refused
    signer: str | None = None
    artifact_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "reason": self.reason,
            "epistemicLevel": self.epistemic_level,
            "signer": self.signer,
            "artifactId": self.artifact_id,
        }


def default_attestation_verifier(attestation: dict[str, Any], trusted_key: str | None) -> bool:
    """Real minisign verification of the attestation's signatureRef. FAIL CLOSED.

    Returns False — never raises, never assumes — when the trusted key is absent,
    the minisign binary is unavailable, the signature is missing, or verification
    does not pass. The signed message is the canonical binding line
    ``<artifactId>\\n`` so a signature is valid only for the exact artifact it names.
    """
    if not trusted_key:
        return False
    signature = attestation.get("signatureRef")
    artifact_id = attestation.get("artifactId")
    if not signature or not artifact_id:
        return False
    if shutil.which("minisign") is None:
        return False
    try:
        with tempfile.TemporaryDirectory() as d:
            msg = Path(d) / "subject"
            sig = Path(d) / "subject.minisig"
            msg.write_text(f"{artifact_id}\n", encoding="utf-8")
            sig.write_text(signature if signature.endswith("\n") else signature + "\n", encoding="utf-8")
            proc = subprocess.run(
                ["minisign", "-V", "-P", trusted_key, "-m", str(msg), "-x", str(sig)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return proc.returncode == 0
    except Exception:
        return False


def verify_release_attestation(
    attestation: dict[str, Any] | None,
    *,
    org: str,
    content_view: str,
    version: str,
    trusted_key: str | None,
    verifier: Verifier | None = None,
) -> AttestationDecision:
    """Decide whether `attestation` authorizes a switch to `version`. Fail closed."""
    verify = verifier or default_attestation_verifier

    if attestation is None:
        return AttestationDecision(
            ok=False,
            reason=f"no release attestation for version {version!r} — absence returns Speculative, not Proved",
            epistemic_level="Speculative",
        )

    missing = [k for k in REQUIRED_FIELDS if not attestation.get(k)]
    if missing:
        return AttestationDecision(
            ok=False,
            reason=f"attestation missing required SignedArtifact field(s) {missing} — unsigned or malformed",
            epistemic_level="Speculative",
            signer=attestation.get("signer"),
        )

    expected = expected_artifact_id(org, content_view, version)
    if attestation["artifactId"] != expected:
        return AttestationDecision(
            ok=False,
            reason=(
                f"attestation artifactId {attestation['artifactId']!r} does not bind version "
                f"{version!r} (expected {expected!r}) — an attestation for another artifact is "
                f"not authorization for this switch"
            ),
            epistemic_level="Speculative",
            signer=attestation.get("signer"),
        )

    if not verify(attestation, trusted_key):
        return AttestationDecision(
            ok=False,
            reason=(
                "signature did not verify against the trusted key (or the verifier could not run — "
                "fail closed: a gate that cannot fail is not a gate)"
            ),
            epistemic_level="Speculative",
            signer=attestation.get("signer"),
            artifact_id=expected,
        )

    return AttestationDecision(
        ok=True,
        reason="release attestation verified and bound to this exact version",
        epistemic_level="Proved",
        signer=attestation.get("signer"),
        artifact_id=expected,
    )


def make_release_attestation(
    *,
    org: str,
    content_view: str,
    version: str,
    signer: str,
    signature_ref: str,
    algorithm: str = "minisign-ed25519",
    issuer: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Construct a SignedArtifact-shaped release attestation bound to a version.

    Used by tests and by the build/promote pipeline (the paired producer WO).
    """
    return {
        "schema": ATTESTATION_SCHEMA,
        "artifactId": expected_artifact_id(org, content_view, version),
        "signer": signer,
        "algorithm": algorithm,
        "timestamp": timestamp or utc_now(),
        "issuer": issuer,
        "signatureRef": signature_ref,
    }
