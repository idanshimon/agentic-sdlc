"""Trust-boundary tests for authoritative principals and route authorization."""
from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from apps.orchestrator.auth import (
    AuthConfigurationError,
    Principal,
    authorize_mutation,
    principal_from_request,
    validate_auth_configuration,
)


def _request(path: str = "/api/runs/r1/approve", headers: dict[str, str] | None = None) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "method": "POST", "path": path, "headers": raw})


def test_disabled_mode_is_explicit_development_principal(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "disabled")
    principal = principal_from_request(_request())
    assert principal.source == "disabled"
    assert principal.subject == "development-principal"
    assert "admin" in principal.roles
    assert principal.can_access_team("any-team")


def test_production_trusted_headers_require_proxy_secret(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "trusted_headers")
    monkeypatch.setenv("EXECUTION_PROFILE", "production")
    monkeypatch.delenv("TRUSTED_PROXY_SECRET", raising=False)
    with pytest.raises(AuthConfigurationError, match="TRUSTED_PROXY_SECRET"):
        validate_auth_configuration()


def test_production_refuses_disabled_auth(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "disabled")
    monkeypatch.setenv("EXECUTION_PROFILE", "production")
    with pytest.raises(AuthConfigurationError, match="AUTH_MODE=disabled"):
        validate_auth_configuration()


def test_trusted_headers_require_subject_roles_and_teams(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "trusted_headers")
    principal = principal_from_request(_request(headers={
        "x-auth-subject": "operator@example.com",
        "x-auth-kind": "human",
        "x-auth-roles": "operator,persona_owner",
        "x-auth-teams": "team-a,team-b",
    }))
    assert principal.subject == "operator@example.com"
    assert principal.roles == frozenset({"operator", "persona_owner"})
    assert principal.teams == frozenset({"team-a", "team-b"})
    assert principal.can_access_team("team-b")
    assert not principal.can_access_team("team-c")


def test_trusted_headers_missing_identity_is_401(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "trusted_headers")
    with pytest.raises(HTTPException) as exc:
        principal_from_request(_request())
    assert exc.value.status_code == 401


def test_operator_cannot_use_admin_route():
    principal = Principal(
        subject="op", kind="human", roles=frozenset({"operator"}),
        teams=frozenset({"team-a"}), source="trusted_headers",
    )
    with pytest.raises(HTTPException) as exc:
        authorize_mutation(principal, "/api/admin/runs/r1/mark_failed")
    assert exc.value.status_code == 403


def test_github_workload_bearer_token_is_narrowly_mapped(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "trusted_headers")
    monkeypatch.setenv("REVIEW_LOOP_DISPATCH_TOKEN", "dispatch-test-token")
    principal = principal_from_request(_request(
        path="/api/review-loops",
        headers={"authorization": "Bearer dispatch-test-token"},
    ))
    assert principal.kind == "workload"
    assert principal.roles == frozenset({"github_workload"})
    authorize_mutation(principal, "/api/review-loops")
    with pytest.raises(HTTPException):
        authorize_mutation(principal, "/api/admin/runs/r1/mark_failed")


def test_github_workload_is_limited_to_dispatch():
    principal = Principal(
        subject="github-actions", kind="workload", roles=frozenset({"github_workload"}),
        teams=frozenset(), source="trusted_headers",
    )
    authorize_mutation(principal, "/api/review-loops")
    with pytest.raises(HTTPException):
        authorize_mutation(principal, "/api/config/reload")


def test_approve_derives_actor_and_enforces_team(monkeypatch):
    from fastapi.testclient import TestClient
    from apps.orchestrator.main import app, _runs
    from apps.orchestrator.models import AmbiguityCard, ResolutionOption, RunState, RunStatus, Stage

    monkeypatch.setenv("AUTH_MODE", "trusted_headers")
    card = AmbiguityCard(
        card_id="card-auth", title="scope", detail="scope gap",
        ambiguity_class="scope-resolution",
        options=[ResolutionOption(
            label="A", resolution="Use A", rationale="test",
            downstream_impact="test", recommended=True,
        )],
    )
    run = RunState(
        run_id="run-auth", team_id="team-a", status=RunStatus.AWAITING_GATE,
        current_stage=Stage.RESOLVER, cards=[card],
    )
    _runs[run.run_id] = run
    client = TestClient(app)
    headers = {
        "x-auth-subject": "real.operator@example.com",
        "x-auth-kind": "human",
        "x-auth-roles": "operator",
        "x-auth-teams": "team-a",
        "idempotency-key": "auth-approve-1",
    }
    try:
        response = client.post(
            "/api/runs/run-auth/approve", headers=headers,
            json={
                "card_id": "card-auth", "decision_kind": "accept",
                "actor": "spoofed@example.com",
            },
        )
        assert response.status_code == 200, response.text
        assert run.decisions[0].actor == "real.operator@example.com"

        denied = client.post(
            "/api/runs/run-auth/reject",
            headers={**headers, "x-auth-teams": "team-b"},
            json={"card_id": "card-auth", "decision_kind": "reject"},
        )
        assert denied.status_code == 403
    finally:
        _runs.pop(run.run_id, None)
