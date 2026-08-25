"""Planning-tracker providers — READ-ONLY by construction.

One normalized `WorkItem` shape across every provider (Aha!, Jira, Azure Boards,
generic REST), so adding a provider changes no consumer.

**No write path exists in this capability.** The protocol below exposes exactly
two operations — `resolve` and `probe` — and a spec test asserts no provider
class carries a create/update/transition/close method. Outbound status write-back
is a separate proposal with its own governance analysis.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Optional, Protocol, runtime_checkable

import httpx

from .integrations import Integration
from .work_items import WorkItem

_logger = logging.getLogger("orchestrator.planning_providers")

# Any method name matching these would be a write path. Asserted against in tests.
FORBIDDEN_METHOD_PREFIXES = ("create", "update", "delete", "close", "transition", "write", "post_")

_TIMEOUT = float(os.getenv("PLANNING_PROVIDER_TIMEOUT_S", "8"))


@dataclass(frozen=True)
class ProbeResult:
    """Outcome of a bounded read-only reachability probe.

    `status` is one of verified | failing | unknown. There is deliberately no
    path that returns `verified` without an actual successful call.
    """

    status: str
    reason: str = ""
    identity: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "verified"


@runtime_checkable
class PlanningProvider(Protocol):
    """Read-only contract. Two operations, both non-mutating."""

    name: str

    async def resolve(self, integration: Integration, ref: str) -> Optional[WorkItem]:
        ...

    async def probe(self, integration: Integration) -> ProbeResult:
        ...


def _auth_headers(integration: Integration) -> dict[str, str]:
    """Build auth headers from the REFERENCED env var.

    The value is used to sign the request and is never returned, logged, or
    stored anywhere by this module.
    """
    token = os.getenv(integration.token_env, "").strip() if integration.token_env else ""
    if not token:
        return {}
    if integration.provider == "aha":
        return {"Authorization": f"Bearer {token}"}
    if integration.provider == "azure_boards":
        # Azure DevOps PAT is basic-auth with an empty username.
        import base64

        blob = base64.b64encode(f":{token}".encode()).decode()
        return {"Authorization": f"Basic {blob}"}
    # jira (bearer/PAT) and generic default to bearer.
    return {"Authorization": f"Bearer {token}"}


def _first_str(payload: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        cur: Any = payload
        ok = True
        for part in key.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                ok = False
                break
        if ok and isinstance(cur, (str, int, float)) and str(cur).strip():
            return str(cur).strip()
    return default


class RestPlanningProvider:
    """Template-driven read-only REST provider.

    Every shipped provider is this class with a different `name` — the record
    shape the pipeline needs (id, type, title, body, url) is genuinely the same
    across trackers, and the differences live in the registry's URL templates and
    the response-field aliases below. That is what keeps "add a provider" from
    touching any consumer.
    """

    # Response-field aliases per provider, longest-shot first.
    TITLE_KEYS = ("name", "title", "fields.summary", "subject", "fields.System_Title")
    BODY_KEYS = ("description", "body", "fields.description", "fields.System_Description")
    TYPE_KEYS = ("type", "item_type", "fields.issuetype.name", "fields.System_WorkItemType")

    def __init__(self, name: str) -> None:
        self.name = name

    def _api_url(self, integration: Integration, ref: str) -> str:
        if integration.item_api_template:
            return integration.item_api_template.replace("{ref}", ref)
        if integration.base_url:
            return f"{integration.base_url.rstrip('/')}/{ref}"
        return ""

    async def resolve(self, integration: Integration, ref: str) -> Optional[WorkItem]:
        """Fetch a work item. Returns None on ANY failure — an unreachable or
        unauthorized planning system must never fail the run (spec scenario);
        the caller records the reference as unverified with a reason."""
        url = self._api_url(integration, ref)
        if not url:
            return None
        headers = _auth_headers(integration)
        if not headers:
            return None
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(url, headers=headers)
            if resp.status_code >= 400:
                _logger.warning(
                    "planning provider %s: resolve %s returned HTTP %s",
                    self.name, ref, resp.status_code,
                )
                return None
            payload = resp.json()
        except Exception as exc:  # network, json, anything
            _logger.warning("planning provider %s: resolve %s failed: %s", self.name, ref, exc)
            return None

        if not isinstance(payload, dict):
            return None
        # Trackers commonly wrap the record (Aha! -> {"feature": {...}}).
        record = payload
        for wrapper in ("feature", "idea", "epic", "requirement", "issue", "value", "data"):
            inner = payload.get(wrapper)
            if isinstance(inner, dict):
                record = inner
                break

        return WorkItem(
            id=_first_str(record, "reference_num", "key", "id", default=ref),
            item_type=_first_str(record, *self.TYPE_KEYS, default="unknown").lower(),
            title=_first_str(record, *self.TITLE_KEYS),
            body=_first_str(record, *self.BODY_KEYS),
            url=_first_str(record, "url", "html_url", "_links.html.href")
            or integration.resolve_item_url(ref),
        )

    async def probe(self, integration: Integration) -> ProbeResult:
        """Bounded read-only reachability check.

        Returns `unknown` (never `verified`) when the probe cannot be attempted —
        no credential or no base URL means we learned nothing.
        """
        if not integration.credential_present:
            return ProbeResult("unknown", "no credential present for the referenced env var")
        base = integration.base_url.rstrip("/") if integration.base_url else ""
        if not base:
            return ProbeResult("unknown", "no base_url configured to probe")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(base, headers=_auth_headers(integration))
        except Exception as exc:
            return ProbeResult("failing", f"request failed: {type(exc).__name__}")
        if resp.status_code in (401, 403):
            return ProbeResult("failing", f"authentication rejected (HTTP {resp.status_code})")
        if resp.status_code >= 500:
            return ProbeResult("failing", f"planning system error (HTTP {resp.status_code})")
        if resp.status_code >= 400:
            return ProbeResult("failing", f"probe returned HTTP {resp.status_code}")
        return ProbeResult("verified", f"reachable (HTTP {resp.status_code})", integration.identity)


class GitHubCodeHostProvider:
    """Read-only probe for the code host. Uses the whoami-class /user call so a
    green status means the delivery identity genuinely authenticated."""

    name = "github"

    async def probe(self, integration: Integration) -> ProbeResult:
        if not integration.credential_present:
            return ProbeResult("unknown", "no credential present for the referenced env var")
        token = os.getenv(integration.token_env, "").strip()
        base = (integration.base_url or "https://api.github.com").rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(
                    f"{base}/user",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                    },
                )
        except Exception as exc:
            return ProbeResult("failing", f"request failed: {type(exc).__name__}")
        if resp.status_code in (401, 403):
            return ProbeResult("failing", f"authentication rejected (HTTP {resp.status_code})")
        if resp.status_code >= 400:
            return ProbeResult("failing", f"probe returned HTTP {resp.status_code}")
        try:
            login = str(resp.json().get("login", "")).strip()
        except Exception:
            login = ""
        return ProbeResult("verified", "authenticated to the code host", login)

    async def resolve(self, integration: Integration, ref: str) -> Optional[WorkItem]:
        return None


_PLANNING_PROVIDERS: dict[str, Any] = {
    "aha": RestPlanningProvider("aha"),
    "jira": RestPlanningProvider("jira"),
    "azure_boards": RestPlanningProvider("azure_boards"),
    "generic": RestPlanningProvider("generic"),
}
_CODE_HOST_PROVIDERS: dict[str, Any] = {"github": GitHubCodeHostProvider()}


def get_provider(integration: Integration) -> Optional[Any]:
    """Resolve the provider implementation for an integration, or None."""
    if integration.kind == "planning_tracker":
        return _PLANNING_PROVIDERS.get(integration.provider)
    if integration.kind == "code_host":
        return _CODE_HOST_PROVIDERS.get(integration.provider)
    return None


async def probe_integration(integration: Integration) -> ProbeResult:
    """Probe an integration, degrading to `unknown` when no probe is implemented.
    Never raises — an integration test must not be able to take down the API."""
    provider = get_provider(integration)
    if provider is None or not hasattr(provider, "probe"):
        return ProbeResult("unknown", "no reachability probe implemented for this provider")
    try:
        return await provider.probe(integration)
    except Exception as exc:  # pragma: no cover - defensive
        _logger.warning("probe of %s raised: %s", integration.id, exc)
        return ProbeResult("failing", f"probe raised {type(exc).__name__}")


async def resolve_work_item(integration: Integration, ref: str) -> Optional[WorkItem]:
    """Resolve a work item read-only. None on any failure (never raises)."""
    provider = get_provider(integration)
    if provider is None or not hasattr(provider, "resolve"):
        return None
    try:
        return await provider.resolve(integration, ref)
    except Exception as exc:  # pragma: no cover - defensive
        _logger.warning("resolve of %s/%s raised: %s", integration.id, ref, exc)
        return None
