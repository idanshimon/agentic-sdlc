"""Azure AI Foundry provider — supports two deployment shapes.

Foundry can serve models in either schema depending on the deployment:
  * foundry-oai       — OpenAI chat completions schema (gpt-4.1, Phi, Mistral, etc.)
  * foundry-anthropic — native Anthropic /messages schema (Claude deployments)

One class, shape switch via constructor arg. Endpoint construction differs
per shape; auth model is the same (Foundry API key or APIM passthrough).

Phase 1 honesty: APIM-fronted Foundry passthrough is scaffolded. The default
working path is `via_apim=False` against the Foundry deployment URL directly.
"""
from __future__ import annotations

import logging
import os
from typing import Literal, Optional

import httpx

from ..config import settings
from .base import ChatResponse, Provider

_logger = logging.getLogger("orchestrator.providers.foundry")

FoundryShape = Literal["foundry-oai", "foundry-anthropic"]


class FoundryProvider(Provider):
    """Azure AI Foundry — OpenAI-schema or Anthropic-messages-schema deployments."""
    name = "foundry"

    def __init__(
        self,
        shape: FoundryShape = "foundry-oai",
        via_apim: bool = False,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        super().__init__(via_apim=via_apim)
        if shape not in ("foundry-oai", "foundry-anthropic"):
            raise ValueError(f"unknown Foundry shape: {shape!r}")
        self.shape = shape
        if via_apim:
            # Phase 1 scaffolding — APIM is expected to route /foundry-oai or
            # /foundry-anthropic paths to the backend deployment pool.
            self.base_url = (base_url or settings.apim_base_url).rstrip("/")
            self.api_key = settings.apim_subscription_key or ""
        else:
            self.base_url = (base_url or os.environ.get("FOUNDRY_BASE_URL", "")).rstrip("/")
            self.api_key = api_key or os.environ.get("FOUNDRY_API_KEY", "")

    def _endpoint(self, model: str) -> str:
        if self.shape == "foundry-oai":
            # OpenAI-compatible: POST {base}/openai/deployments/{model}/chat/completions
            return f"{self.base_url}/openai/deployments/{model}/chat/completions?api-version=2024-10-21"
        # foundry-anthropic native messages
        return f"{self.base_url}/v1/messages"

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.2,
        headers: Optional[dict[str, str]] = None,
    ) -> ChatResponse:
        url = self._endpoint(model)
        req_headers = {"Content-Type": "application/json", **(headers or {})}
        if self.via_apim and self.api_key:
            req_headers["Ocp-Apim-Subscription-Key"] = self.api_key
        elif self.api_key:
            req_headers["api-key"] = self.api_key

        if self.shape == "foundry-oai":
            body: dict = {
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        else:
            # Split out system; Anthropic uses top-level `system`, not a role.
            sys_text = ""
            user_msgs: list[dict] = []
            for m in messages:
                if m.get("role") == "system":
                    sys_text = (sys_text + "\n" + m.get("content", "")).strip()
                else:
                    user_msgs.append({"role": m.get("role", "user"), "content": m.get("content", "")})
            req_headers.setdefault("anthropic-version", "2023-06-01")
            body = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "system": sys_text,
                "messages": user_msgs,
            }

        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(url, headers=req_headers, json=body)
            r.raise_for_status()
            data = r.json()

        if self.shape == "foundry-oai":
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
            usage = data.get("usage", {}) or {}
            return ChatResponse(
                text=text,
                prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
                completion_tokens=int(usage.get("completion_tokens", 0) or 0),
                raw={"shape": self.shape, "via_apim": self.via_apim},
            )
        # anthropic shape
        text = ""
        for block in data.get("content", []) or []:
            if block.get("type") == "text":
                text += block.get("text", "")
        usage = data.get("usage", {}) or {}
        return ChatResponse(
            text=text,
            prompt_tokens=int(usage.get("input_tokens", 0) or 0),
            completion_tokens=int(usage.get("output_tokens", 0) or 0),
            raw={"shape": self.shape, "via_apim": self.via_apim},
        )
