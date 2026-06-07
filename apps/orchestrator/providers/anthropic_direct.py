"""Anthropic direct API provider.

Endpoint: https://api.anthropic.com/v1/messages
Auth:     x-api-key header (not Bearer)

Phase 1: via_apim=True is scaffolding — APIM backend pool for api.anthropic.com
is not configured today. See docs/PROVIDERS.md#apim-config.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

from ..config import settings
from .base import ChatResponse, Provider

_logger = logging.getLogger("orchestrator.providers.anthropic_direct")


class AnthropicDirectProvider(Provider):
    name = "anthropic"

    def __init__(
        self,
        via_apim: bool = False,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        super().__init__(via_apim=via_apim)
        if via_apim:
            self.base_url = (base_url or settings.apim_base_url).rstrip("/")
        else:
            self.base_url = (base_url or os.environ.get(
                "ANTHROPIC_DIRECT_BASE_URL", "https://api.anthropic.com",
            )).rstrip("/")
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 8192,
        temperature: float = 0.2,
        headers: Optional[dict[str, str]] = None,
    ) -> ChatResponse:
        if not self.api_key:
            raise RuntimeError("Anthropic direct provider requires ANTHROPIC_API_KEY")
        sys_text = ""
        user_msgs: list[dict] = []
        for m in messages:
            if m.get("role") == "system":
                sys_text = (sys_text + "\n" + m.get("content", "")).strip()
            else:
                user_msgs.append({"role": m.get("role", "user"), "content": m.get("content", "")})
        req_headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
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
