"""GitHub App client — JWT signing + installation token fetch.

Why GitHub App not PAT:
  - App tokens are scoped (per-installation, per-repo, per-permission)
  - Rotation is automatic (token TTL ~1h)
  - GH audit log attributes events to the App, not a user
  - Compliance gets clean attribution

Auth flow:
  1. Sign a JWT with the App private key (RS256, 10-min TTL)
  2. Exchange JWT for an installation access token (~1h TTL)
  3. Use installation token for all REST calls

Installation token caching: in-memory, refreshed on expiry.
"""
from __future__ import annotations
import asyncio
import logging
import time
from typing import Optional

import httpx
import jwt  # PyJWT

_logger = logging.getLogger("orchestrator.github_app_client")


class GitHubAppClient:
    """Fetch installation tokens for a GitHub App installation."""

    def __init__(self, app_id: str, private_key: str, installation_id: int):
        self._app_id = app_id
        self._private_key = private_key
        self._installation_id = installation_id
        self._token_cache: Optional[tuple[str, float]] = None  # (token, expires_at_unix)
        self._lock = asyncio.Lock()

    async def get_installation_token(self) -> str:
        """Return a valid installation access token, fetching/refreshing as needed."""
        async with self._lock:
            if self._token_cache is not None:
                token, expires_at = self._token_cache
                if expires_at > time.time() + 60:  # 60s buffer
                    return token
            return await self._fetch_new_token()

    async def _fetch_new_token(self) -> str:
        jwt_token = self._sign_jwt()
        async with httpx.AsyncClient(
            base_url="https://api.github.com",
            timeout=15.0,
        ) as client:
            resp = await client.post(
                f"/app/installations/{self._installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        token = data["token"]
        # GH installation tokens TTL ~1h. Parse expires_at if present.
        expires_at = time.time() + 3500  # safe default ~58min
        if "expires_at" in data:
            try:
                from datetime import datetime, timezone as tz
                expires_at = (
                    datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
                    .replace(tzinfo=tz.utc)
                    .timestamp()
                )
            except Exception:
                pass
        self._token_cache = (token, expires_at)
        _logger.info("fetched installation token; expires at %s", expires_at)
        return token

    def _sign_jwt(self) -> str:
        """Sign a 10-minute JWT with the App private key."""
        now = int(time.time())
        payload = {
            "iat": now - 60,    # 60s leeway for clock skew
            "exp": now + 540,   # 9-minute TTL (GH allows max 10)
            "iss": self._app_id,
        }
        return jwt.encode(payload, self._private_key, algorithm="RS256")
