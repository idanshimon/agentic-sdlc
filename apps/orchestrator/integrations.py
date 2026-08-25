"""Integrations registry — the external-systems plane.

Part of the `add-enterprise-integrations-plane` capability. Declares which
external systems this instance is wired to (code host, planning tracker), under
which identity, with which scopes — and NOTHING about their credentials beyond a
reference to where the credential lives.

Design posture (identical to org_model / autonomy / model_policy):

    python default (empty) < ./integrations.yaml or /app/integrations.yaml
                           < INTEGRATIONS_PATH env

Activation is OPT-IN. The repo's `config/integrations.yaml.example` TEMPLATE is
deliberately NOT auto-discovered, so deploying the image changes nothing until an
operator activates a registry.

Hard rules enforced here (openspec spec scenarios):

  - **Credentials are referenced, never stored.** An entry naming an inline
    `token`/`secret`/`password`/`api_key` is REFUSED at load, and no view this
    module produces ever contains credential material. `token_env` names the
    environment variable; `credential_present` reports only its presence.
  - **Unknown providers are refused** — but one bad entry must not take the whole
    registry down, so well-formed siblings still load.
  - **Malformed file degrades loudly to not-loaded**, never half-applied.
  - **Honest status.** `configured` != `verified`. Nothing in this module can
    produce `verified`; only an actual successful probe (integrations_probe) may
    upgrade a status, and a probe that cannot run yields `unknown`.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional

import yaml

_logger = logging.getLogger("orchestrator.integrations")

# Integration kinds this capability understands.
KIND_CODE_HOST = "code_host"
KIND_PLANNING_TRACKER = "planning_tracker"
KNOWN_KINDS = frozenset({KIND_CODE_HOST, KIND_PLANNING_TRACKER})

# Providers implemented per kind. An entry naming anything else is refused at
# load with its reason recorded, rather than silently accepted and then failing
# at the first probe.
KNOWN_PROVIDERS: dict[str, frozenset[str]] = {
    KIND_CODE_HOST: frozenset({"github"}),
    KIND_PLANNING_TRACKER: frozenset({"aha", "jira", "azure_boards", "generic"}),
}

# Keys that would mean a credential was pasted into the YAML. Their presence is a
# validation failure — the registry is a git-adjacent config object and must never
# be able to hold secret material.
FORBIDDEN_CREDENTIAL_KEYS = frozenset(
    {"token", "secret", "password", "api_key", "apikey", "client_secret", "pat",
     "connection_string"}
)

Status = Literal["unconfigured", "configured", "verified", "failing", "unknown"]


class IntegrationValidationError(Exception):
    """Raised for an entry that cannot be admitted to the registry."""


@dataclass(frozen=True)
class Integration:
    """One declared external system.

    `status` here is only ever `unconfigured` or `configured` — this module
    cannot mint `verified`. That word is reserved for a real probe result.
    """

    id: str
    kind: str
    provider: str
    display_name: str = ""
    base_url: str = ""
    identity: str = ""                       # the owning principal (app/PAT owner/MI)
    scopes: tuple[str, ...] = ()
    token_env: str = ""                      # NAME of the env var, never its value
    # Planning trackers only: how to turn a work-item ref into a URL, and how to
    # fetch it. `{ref}` is the substitution token.
    item_url_template: str = ""
    item_api_template: str = ""
    # Code hosts only: the delivery target.
    target_repo: str = ""
    notes: str = ""

    @property
    def credential_present(self) -> bool:
        """True when the referenced env var actually holds a value.

        Reports presence only. The value is never read into any returned shape.
        """
        if not self.token_env:
            return False
        return bool(os.getenv(self.token_env, "").strip())

    @property
    def status(self) -> Status:
        """Declared-state status. Never `verified` — see module docstring."""
        if not self.credential_present:
            return "unconfigured"
        return "configured"

    def resolve_item_url(self, ref: str) -> str:
        """Render the work-item URL for `ref`, or "" when no template is set."""
        if not self.item_url_template or not ref:
            return ""
        return self.item_url_template.replace("{ref}", str(ref).strip())

    def redacted(self) -> dict[str, Any]:
        """Operator-safe view. Contains no credential material by construction —
        `token_env` is a variable NAME, and only its presence is reported."""
        return {
            "id": self.id,
            "kind": self.kind,
            "provider": self.provider,
            "display_name": self.display_name or self.id,
            "base_url": self.base_url,
            "identity": self.identity,
            "scopes": list(self.scopes),
            "token_env": self.token_env,
            "credential_present": self.credential_present,
            "status": self.status,
            "verified": False,
            "item_url_template": self.item_url_template,
            "target_repo": self.target_repo,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class IntegrationsRegistry:
    loaded: bool = False
    source_path: str = ""
    integrations: tuple[Integration, ...] = ()
    # Entries refused at load, with the reason. Surfaced so a typo is a visible
    # finding rather than a silently missing integration.
    rejected: tuple[dict[str, str], ...] = ()
    error: str = ""

    def get(self, integration_id: str) -> Optional[Integration]:
        for item in self.integrations:
            if item.id == integration_id:
                return item
        return None

    def by_kind(self, kind: str) -> tuple[Integration, ...]:
        return tuple(i for i in self.integrations if i.kind == kind)

    def planning_tracker(self, name: str = "") -> Optional[Integration]:
        """Resolve a planning tracker by id/provider, else the sole one if unique."""
        trackers = self.by_kind(KIND_PLANNING_TRACKER)
        if name:
            key = name.strip().lower()
            for t in trackers:
                if t.id.lower() == key or t.provider.lower() == key:
                    return t
            return None
        return trackers[0] if len(trackers) == 1 else None

    def redacted(self) -> dict[str, Any]:
        return {
            "loaded": self.loaded,
            "source_path": self.source_path,
            "error": self.error,
            "integrations": [i.redacted() for i in self.integrations],
            "rejected": [dict(r) for r in self.rejected],
        }


def _candidate_paths() -> list[Path]:
    """Activation is OPT-IN — the repo config/integrations.yaml.example TEMPLATE
    is NOT auto-discovered. A fresh deploy reports every integration surface as
    unconfigured until an operator sets INTEGRATIONS_PATH or drops
    /app/integrations.yaml (or ./integrations.yaml)."""
    env_path = os.getenv("INTEGRATIONS_PATH")
    paths: list[Path] = []
    if env_path:
        paths.append(Path(env_path))
    paths.extend([Path("/app/integrations.yaml"), Path("integrations.yaml")])
    return paths


def _as_tuple(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, list):
        return ()
    return tuple(str(x).strip() for x in raw if str(x).strip())


def _parse_entry(raw: object) -> Integration:
    """Validate one entry. Raises IntegrationValidationError with a reason."""
    if not isinstance(raw, dict):
        raise IntegrationValidationError("entry is not a mapping")

    # Credential material must never live in this file.
    offending = sorted(k for k in raw if str(k).strip().lower() in FORBIDDEN_CREDENTIAL_KEYS)
    if offending:
        raise IntegrationValidationError(
            f"inline credential field(s) {', '.join(offending)} are not allowed — "
            f"reference the credential with token_env instead"
        )

    ident = str(raw.get("id", "")).strip()
    if not ident:
        raise IntegrationValidationError("entry is missing a required 'id'")

    kind = str(raw.get("kind", "")).strip()
    if kind not in KNOWN_KINDS:
        raise IntegrationValidationError(
            f"unknown kind {kind!r} (known: {', '.join(sorted(KNOWN_KINDS))})"
        )

    provider = str(raw.get("provider", "")).strip().lower()
    allowed = KNOWN_PROVIDERS.get(kind, frozenset())
    if provider not in allowed:
        raise IntegrationValidationError(
            f"unknown provider {provider!r} for kind {kind!r} "
            f"(known: {', '.join(sorted(allowed))})"
        )

    return Integration(
        id=ident,
        kind=kind,
        provider=provider,
        display_name=str(raw.get("display_name", "") or "").strip(),
        base_url=str(raw.get("base_url", "") or "").strip(),
        identity=str(raw.get("identity", "") or "").strip(),
        scopes=_as_tuple(raw.get("scopes")),
        token_env=str(raw.get("token_env", "") or "").strip(),
        item_url_template=str(raw.get("item_url_template", "") or "").strip(),
        item_api_template=str(raw.get("item_api_template", "") or "").strip(),
        target_repo=str(raw.get("target_repo", "") or "").strip(),
        notes=str(raw.get("notes", "") or "").strip(),
    )


def load_integrations(path: Optional[str] = None) -> IntegrationsRegistry:
    """Load integrations.yaml.

    Absent  -> unloaded registry (every surface reports `unconfigured`); pipeline
               behaviour is byte-identical to pre-capability.
    Malformed -> unloaded registry WITH an error string, logged loudly. Never a
               half-applied registry.
    """
    search = [Path(path)] if path else _candidate_paths()
    for p in search:
        try:
            if not p.is_file():
                continue
        except OSError:  # pragma: no cover - unusual fs states
            continue
        try:
            data = yaml.safe_load(p.read_text()) or {}
        except Exception as exc:
            _logger.error(
                "integrations: %s is malformed (%s) — registry NOT loaded "
                "(bootstrap/unconfigured mode)", p, exc,
            )
            return IntegrationsRegistry(loaded=False, source_path=str(p), error=str(exc))

        if not isinstance(data, dict):
            msg = "top-level document is not a mapping"
            _logger.error("integrations: %s %s — registry NOT loaded", p, msg)
            return IntegrationsRegistry(loaded=False, source_path=str(p), error=msg)

        raw_items = data.get("integrations", [])
        if not isinstance(raw_items, list):
            msg = "'integrations' must be a list"
            _logger.error("integrations: %s %s — registry NOT loaded", p, msg)
            return IntegrationsRegistry(loaded=False, source_path=str(p), error=msg)

        parsed: list[Integration] = []
        rejected: list[dict[str, str]] = []
        seen: set[str] = set()
        for raw in raw_items:
            try:
                item = _parse_entry(raw)
            except IntegrationValidationError as exc:
                ref = ""
                if isinstance(raw, dict):
                    ref = str(raw.get("id", "") or "")
                # Log the REASON, never the entry (it may be the very thing that
                # wrongly carried a credential).
                _logger.error("integrations: rejected entry %r — %s", ref or "<unnamed>", exc)
                rejected.append({"id": ref or "<unnamed>", "reason": str(exc)})
                continue
            if item.id in seen:
                rejected.append({"id": item.id, "reason": "duplicate id"})
                _logger.error("integrations: rejected duplicate id %r", item.id)
                continue
            seen.add(item.id)
            parsed.append(item)

        _logger.info(
            "integrations: loaded %s (%d integration(s), %d rejected)",
            p, len(parsed), len(rejected),
        )
        return IntegrationsRegistry(
            loaded=True,
            source_path=str(p),
            integrations=tuple(parsed),
            rejected=tuple(rejected),
        )

    _logger.info("integrations: no integrations.yaml found — unconfigured (bootstrap) mode")
    return IntegrationsRegistry(loaded=False)


# Module-level singleton, mirroring model_policy.MODEL_POLICY / autonomy.AUTONOMY_MATRIX.
INTEGRATIONS: IntegrationsRegistry = load_integrations()


def reload_integrations(path: Optional[str] = None) -> IntegrationsRegistry:
    global INTEGRATIONS
    INTEGRATIONS = load_integrations(path)
    return INTEGRATIONS
