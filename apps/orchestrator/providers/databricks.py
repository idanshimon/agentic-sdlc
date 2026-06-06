"""Databricks-hosted Anthropic provider.

Endpoint shape:
    POST {ANTHROPIC_BASE_URL}/v1/messages
Auth: Bearer {ANTHROPIC_AUTH_TOKEN}
Header: x-databricks-use-coding-agent-mode: true  (Coding Agent mode)

Phase 1 honesty: APIM passthrough policy for Databricks is scaffolded but not
fully configured today. via_apim=True is a no-op path until the APIM backend
pool is wired (see docs/PROVIDERS.md#apim-config).
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

from ..config import settings
from .base import ChatResponse, Provider

_logger = logging.getLogger("orchestrator.providers.databricks")


class DatabricksAnthropicProvider(Provider):
    name = "databricks"

    def __init__(
        self,
        via_apim: bool = False,
        base_url: Optional[str] = None,
        auth_token: Optional[str] = None,
    ) -> None:
        super().__init__(via_apim=via_apim)
        if via_apim:
            self.base_url = (base_url or settings.apim_base_url).rstrip("/")
            self.auth_token = settings.apim_subscription_key or ""
        else:
            self.base_url = (base_url or os.environ.get("ANTHROPIC_BASE_URL", "")).rstrip("/")
            self.auth_token = auth_token or os.environ.get("ANTHROPIC_AUTH_TOKEN", "")

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.2,
        headers: Optional[dict[str, str]] = None,
    ) -> ChatResponse:
        if not self.base_url or not self.auth_token:
            raise RuntimeError(
                "Databricks provider requires ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN"
            )
        sys_text = ""
        user_msgs: list[dict] = []
        for m in messages:
            if m.get("role") == "system":
                sys_text = (sys_text + "\n" + m.get("content", "")).strip()
            else:
                user_msgs.append({"role": m.get("role", "user"), "content": m.get("content", "")})

        req_headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
            "x-databricks-use-coding-agent-mode": "true",
            **(headers or {}),
        }
        if self.via_apim and settings.apim_subscription_key:
            req_headers["Ocp-Apim-Subscription-Key"] = settings.apim_subscription_key

        body = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": sys_text,
            "messages": user_msgs,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(f"{self.base_url}/v1/messages", headers=req_headers, json=body)
            r.raise_for_status()
            data = r.json()

        text = ""
        for block in data.get("content", []) or []:
            if block.get("type") == "text":
                text += block.get("text", "")
        usage = data.get("usage", {}) or {}
        return ChatResponse(
            text=text,
            prompt_tokens=int(usage.get("input_tokens", 0) or 0),
            completion_tokens=int(usage.get("output_tokens", 0) or 0),
            raw={"via_apim": self.via_apim},
        )
