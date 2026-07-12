"""Authentication and authorization boundary for orchestrator HTTP mutations.

Production supports validated upstream identity headers (for EasyAuth/proxies) and
keeps disabled mode explicit for local tests only. Route functions still perform
resource/team checks; this module establishes who is calling and the coarse role.
"""
from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from typing import Literal

from fastapi import HTTPException, Request

Role = Literal[
    "operator", "persona_owner", "standards_reviewer", "release_manager",
    "admin", "github_workload",
]


class AuthConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Principal:
    subject: str
    kind: Literal["human", "workload"]
    roles: frozenset[str]
    teams: frozenset[str]
    source: Literal["disabled", "trusted_headers", "entra", "dispatch_token"]

    def has_any_role(self, *roles: str) -> bool:
        return "admin" in self.roles or bool(self.roles.intersection(roles))

    def can_access_team(self, team_id: str) -> bool:
        return "admin" in self.roles or "*" in self.teams or team_id in self.teams


def _csv(value: str | None) -> frozenset[str]:
    return frozenset(part.strip() for part in (value or "").split(",") if part.strip())


def validate_auth_configuration() -> None:
    auth_mode = os.getenv("AUTH_MODE", "disabled").strip().lower()
    profile = os.getenv("EXECUTION_PROFILE", "development").strip().lower()
    if profile == "production" and auth_mode == "disabled":
        raise AuthConfigurationError("production refuses AUTH_MODE=disabled")
    if profile == "production" and auth_mode == "trusted_headers":
        proxy_secret = os.getenv("TRUSTED_PROXY_SECRET", "")
        if not proxy_secret:
            raise AuthConfigurationError(
                "production trusted_headers requires TRUSTED_PROXY_SECRET from a validating ingress"
            )
    if auth_mode not in {"disabled", "trusted_headers", "entra"}:
        raise AuthConfigurationError(f"unsupported AUTH_MODE={auth_mode!r}")
    if auth_mode == "entra":
        # JWT validation is intentionally not approximated with unsigned decoding.
        # Deployment must use EasyAuth/trusted headers until a verifier is configured.
        raise AuthConfigurationError(
            "AUTH_MODE=entra requires a configured JWT verifier; use trusted_headers behind EasyAuth"
        )


def principal_from_request(request: Request) -> Principal:
    mode = os.getenv("AUTH_MODE", "disabled").strip().lower()
    if mode == "disabled":
        return Principal(
            subject="development-principal",
            kind="human",
            roles=frozenset({"admin"}),
            teams=frozenset({"*"}),
            source="disabled",
        )
    if mode == "entra":
        raise HTTPException(503, "Entra JWT verifier is not configured")
    if mode != "trusted_headers":
        raise HTTPException(503, f"unsupported AUTH_MODE={mode!r}")

    # GitHub Actions uses a separately scoped dispatch credential. It maps to
    # exactly one workload role and is never accepted for human/admin routes.
    if request.url.path == "/api/review-loops":
        authorization = request.headers.get("authorization", "")
        supplied = authorization.removeprefix("Bearer ").strip()
        expected = os.getenv("REVIEW_LOOP_DISPATCH_TOKEN", "")
        if expected and supplied and hmac.compare_digest(supplied, expected):
            return Principal(
                subject="github-actions-review-loop", kind="workload",
                roles=frozenset({"github_workload"}), teams=frozenset(),
                source="dispatch_token",
            )

    subject = request.headers.get("x-auth-subject", "").strip()
    if os.getenv("EXECUTION_PROFILE", "development").strip().lower() == "production":
        supplied_proxy_secret = request.headers.get("x-trusted-proxy-secret", "")
        expected_proxy_secret = os.getenv("TRUSTED_PROXY_SECRET", "")
        if not expected_proxy_secret or not hmac.compare_digest(supplied_proxy_secret, expected_proxy_secret):
            raise HTTPException(401, "request did not pass through the validating identity ingress")
    kind = request.headers.get("x-auth-kind", "human").strip().lower()
    roles = _csv(request.headers.get("x-auth-roles"))
    teams = _csv(request.headers.get("x-auth-teams"))
    if not subject or kind not in {"human", "workload"} or not roles:
        raise HTTPException(401, "validated identity headers are required")
    return Principal(
        subject=subject,
        kind=kind,  # type: ignore[arg-type]
        roles=roles,
        teams=teams,
        source="trusted_headers",
    )


# Coarse route-family authorization. Resource team checks happen after loading the run.
def authorize_mutation(principal: Principal, path: str) -> None:
    if path.startswith("/api/admin/"):
        allowed = principal.has_any_role("admin")
    elif path == "/api/review-loops":
        allowed = principal.has_any_role("github_workload")
    elif path.startswith("/api/review-loops/merge"):
        allowed = principal.has_any_role("release_manager")
    elif path.startswith("/api/config/bundles"):
        allowed = principal.has_any_role("standards_reviewer")
    elif path.startswith("/api/config/"):
        allowed = principal.has_any_role("persona_owner", "standards_reviewer")
    elif "/heal" in path:
        allowed = principal.has_any_role("operator")
    else:
        allowed = principal.has_any_role("operator")
    if not allowed:
        raise HTTPException(403, "principal is not authorized for this mutation")


def require_team(principal: Principal, team_id: str) -> None:
    if not principal.can_access_team(team_id):
        raise HTTPException(403, f"principal is not authorized for team '{team_id}'")
