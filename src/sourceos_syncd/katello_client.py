"""Katello content-view client for sourceos-syncd.

Provides a read-only, stdlib-only HTTP client that queries the Katello API to
discover the current content view version for the device's lifecycle environment
and returns the artifact URLs needed for a Nix-based system update.

Boundary invariant: this module performs no disk writes, no nix invocations, no
nixos-rebuild calls. It returns a ContentViewManifest describing what is available.
Execution of the sync is the caller's responsibility.
"""

from __future__ import annotations

import base64
import json
import ssl
import urllib.request
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class KatelloArtifact:
    name: str
    content_url: str
    sha256: str | None = None
    size_bytes: int | None = None


@dataclass(frozen=True)
class ContentViewManifest:
    """Describes a single published content view version in a lifecycle environment."""

    org: str
    content_view: str
    version: str
    lifecycle_env: str
    katello_url: str
    pulp_content_url: str
    nix_cache_url: str
    artifacts: list[KatelloArtifact] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "org": self.org,
            "content_view": self.content_view,
            "version": self.version,
            "lifecycle_env": self.lifecycle_env,
            "katello_url": self.katello_url,
            "pulp_content_url": self.pulp_content_url,
            "nix_cache_url": self.nix_cache_url,
            "artifacts": [
                {"name": a.name, "content_url": a.content_url,
                 "sha256": a.sha256, "size_bytes": a.size_bytes}
                for a in self.artifacts
            ],
            "description": self.description,
        }


class KatelloClientError(RuntimeError):
    pass


class KatelloContentClient:
    """Read-only Katello API client.

    Connects to a Foreman+Katello instance and discovers the latest content view
    version for a given org, content view name, and lifecycle environment.

    Uses basic auth over HTTPS. For local dev (self-signed cert), pass
    verify_ssl=False.
    """

    API_BASE = "/katello/api/v2"

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        org: str = "SocioProphet",
        verify_ssl: bool = True,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._org = org
        self._auth = base64.b64encode(f"{username}:{password}".encode()).decode()
        self._ctx = ssl.create_default_context() if verify_ssl else self._insecure_ctx()

    @staticmethod
    def _insecure_ctx() -> ssl.SSLContext:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

    def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        url = f"{self._base_url}{self.API_BASE}{path}"
        if params:
            from urllib.parse import urlencode
            url = f"{url}?{urlencode(params)}"
        req = urllib.request.Request(url, headers={
            "Authorization": f"Basic {self._auth}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        })
        try:
            with urllib.request.urlopen(req, context=self._ctx, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise KatelloClientError(f"HTTP {exc.code} fetching {url}: {exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise KatelloClientError(f"Connection error fetching {url}: {exc.reason}") from exc

    def get_org_id(self) -> int:
        data = self._get("/organizations", {"search": f"name={self._org}"})
        results = data.get("results", [])
        if not results:
            raise KatelloClientError(f"Organization not found: {self._org}")
        return int(results[0]["id"])

    def get_content_view_id(self, name: str, org_id: int) -> int:
        data = self._get("/content_views", {
            "organization_id": str(org_id),
            "search": f"name={name}",
        })
        results = data.get("results", [])
        if not results:
            raise KatelloClientError(f"Content view not found: {name}")
        return int(results[0]["id"])

    def get_lifecycle_env_id(self, name: str, org_id: int) -> int:
        data = self._get("/environments", {
            "organization_id": str(org_id),
            "search": f"name={name}",
        })
        results = data.get("results", [])
        if not results:
            raise KatelloClientError(f"Lifecycle environment not found: {name}")
        return int(results[0]["id"])

    def get_latest_version(
        self,
        content_view_name: str,
        lifecycle_env: str,
    ) -> ContentViewManifest:
        """Return the latest content view version promoted to the given lifecycle env."""

        org_id = self.get_org_id()
        cv_id = self.get_content_view_id(content_view_name, org_id)
        env_id = self.get_lifecycle_env_id(lifecycle_env, org_id)

        data = self._get("/content_view_versions", {
            "content_view_id": str(cv_id),
            "environment_id": str(env_id),
            "order": "version DESC",
            "per_page": "1",
        })
        versions = data.get("results", [])
        if not versions:
            raise KatelloClientError(
                f"No version of '{content_view_name}' promoted to '{lifecycle_env}'"
            )
        latest = versions[0]
        version_str = latest.get("version", "unknown")

        # The Pulp content server URL: <base>/<org_label>/content/...
        # For our compose the content port is 8101 (24816 inside container)
        pulp_url = self._base_url.replace(":8443", ":8101").replace(":8080", ":8101")
        nix_cache_url = f"{pulp_url}/{self._org.lower()}/content/sourceos/nix-cache-aarch64-linux/"

        return ContentViewManifest(
            org=self._org,
            content_view=content_view_name,
            version=version_str,
            lifecycle_env=lifecycle_env,
            katello_url=self._base_url,
            pulp_content_url=pulp_url,
            nix_cache_url=nix_cache_url,
            description=latest.get("description", ""),
        )
