"""Read paths enforce the same principal/team boundary as mutations."""
from fastapi.testclient import TestClient

from apps.orchestrator import main as om
from apps.orchestrator.models import RunState


def headers(team: str):
    return {
        "x-auth-subject": "reader@example.com",
        "x-auth-kind": "human",
        "x-auth-roles": "operator",
        "x-auth-teams": team,
    }


def test_run_and_stream_reads_require_authorized_team(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "trusted_headers")
    run = RunState(run_id="read-auth", team_id="team-a")
    om._runs[run.run_id] = run
    om._queues[run.run_id] = __import__("asyncio").Queue()
    client = TestClient(om.app)
    try:
        assert client.get(f"/api/runs/{run.run_id}", headers=headers("team-a")).status_code == 200
        assert client.get(f"/api/runs/{run.run_id}", headers=headers("team-b")).status_code == 403
        assert client.get(f"/api/runs/{run.run_id}/stream", headers=headers("team-b")).status_code == 403
        assert client.get(f"/api/runs/{run.run_id}").status_code == 401
    finally:
        om._runs.pop(run.run_id, None)
        om._queues.pop(run.run_id, None)
