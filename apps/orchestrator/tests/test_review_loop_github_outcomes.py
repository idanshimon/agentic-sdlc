import asyncio

from apps.orchestrator.github_outcomes import publish_review_outcome


class Response:
    def __init__(self, status, body): self.status_code, self.body = status, body
    def json(self): return self.body


class Client:
    def __init__(self): self.posts = []
    async def post(self, url, **kwargs):
        self.posts.append((url, kwargs.get("json")))
        if url.endswith("/check-runs"):
            return Response(201, {"id": 10, "html_url": "https://github/check/10"})
        return Response(201, {"id": 20, "html_url": "https://github/comment/20"})
    async def get(self, url, **kwargs): return Response(200, [])
    async def patch(self, url, **kwargs): raise AssertionError("unexpected patch")


def test_outcome_check_is_bound_to_exact_sha_and_comment_is_marked():
    client = Client()
    result = asyncio.run(publish_review_outcome(
        client=client, repo="owner/repo", pr_number=7, head_sha="a" * 40,
        token="token", disposition="PASSED_AWAITING_MERGE", summary="All checks passed",
    ))
    check_payload = client.posts[0][1]
    comment_payload = client.posts[1][1]
    assert check_payload["head_sha"] == "a" * 40
    assert check_payload["conclusion"] == "neutral"
    assert "agentic-sdlc-review-loop:" in comment_payload["body"]
    assert result.check_id == 10
    assert result.comment_id == 20
