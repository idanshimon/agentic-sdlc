import base64
from types import SimpleNamespace

import asyncio
import pytest

from apps.orchestrator.github_pr_snapshot import SnapshotError, fetch_pr_snapshot


class Response:
    def __init__(self, status, body): self.status_code, self.body = status, body
    def json(self): return self.body


class Client:
    def __init__(self, sha="a" * 40): self.sha, self.calls = sha, []
    async def get(self, url, **kwargs):
        self.calls.append((url, kwargs.get("params")))
        if url.endswith("/pulls/7"):
            return Response(200, {"head": {"sha": self.sha}})
        if url.endswith("/pulls/7/files"):
            page = kwargs["params"]["page"]
            return Response(200, [{"filename": "src/main.py", "status": "modified"}] if page == 1 else [])
        if "/contents/src/main.py" in url:
            return Response(200, {
                "encoding": "base64",
                "content": base64.b64encode(b"print('ok')\n").decode(),
            })
        raise AssertionError(url)


def run(coro): return asyncio.run(coro)


def test_snapshot_verifies_head_and_fetches_exact_bytes():
    snapshot = run(fetch_pr_snapshot(
        repo="owner/repo", pr_number=7, expected_head_sha="a" * 40,
        token="token", client=Client(),
    ))
    assert snapshot.head_sha == "a" * 40
    assert snapshot.files == {"src/main.py": "print('ok')\n"}


def test_snapshot_rejects_stale_head():
    with pytest.raises(SnapshotError, match="stale_head_sha"):
        run(fetch_pr_snapshot(
            repo="owner/repo", pr_number=7, expected_head_sha="b" * 40,
            token="token", client=Client(),
        ))
