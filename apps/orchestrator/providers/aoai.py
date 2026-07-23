"""Azure OpenAI provider — APIM-fronted by default (design.md §1 PDP).

Auth modes (resolved in __init__):
  - via_apim=True: APIM subscription key in the Ocp-Apim-Subscription-Key header.
  - direct + AOAI_API_KEY set: classic api-key auth.
  - direct + no key: KEYLESS via Entra/managed identity — required when the
    AOAI/AIServices account has disableLocalAuth=true (the production-correct
    posture). Uses the workload's user-assigned identity (AZURE_CLIENT_ID) and a
    bearer-token provider scoped to https://cognitiveservices.azure.com/.default.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from openai import AsyncAzureOpenAI

from ..config import settings
from .base import ChatResponse, Provider

_logger = logging.getLogger("orchestrator.providers.aoai")


class AOAIProvider(Provider):
    """Azure OpenAI via APIM (default), a direct api-key, or keyless (Entra MI)."""
    name = "aoai"

    def __init__(self, via_apim: bool = True, base_url: Optional[str] = None) -> None:
        super().__init__(via_apim=via_apim)
        self._token_provider = None  # set only in keyless mode
        if via_apim:
            self.base_url = (base_url or settings.apim_base_url).rsplit("/openai", 1)[0]
            self.api_key = settings.apim_subscription_key or "apim-managed"
            self._extra_headers = (
                {"Ocp-Apim-Subscription-Key": settings.apim_subscription_key}
                if settings.apim_subscription_key else {}
            )
        else:
            self.base_url = base_url or os.environ.get("AOAI_ENDPOINT", "")
            self.api_key = os.environ.get("AOAI_API_KEY", "")
            self._extra_headers = {}
            if not self.api_key:
                # Keyless: the account has disableLocalAuth=true. Authenticate the
                # workload's managed identity and hand AsyncAzureOpenAI a bearer
                # token provider instead of an api-key.
                from azure.identity.aio import (
                    DefaultAzureCredential,
                    get_bearer_token_provider,
                )
                client_id = os.environ.get("AZURE_CLIENT_ID") or None
                cred = DefaultAzureCredential(managed_identity_client_id=client_id)
                self._token_provider = get_bearer_token_provider(
                    cred, "https://cognitiveservices.azure.com/.default"
                )

    def _client(self) -> AsyncAzureOpenAI:
        if self._token_provider is not None:
            return AsyncAzureOpenAI(
                azure_endpoint=self.base_url,
                azure_ad_token_provider=self._token_provider,
                api_version="2024-10-21",
                default_headers=self._extra_headers,
            )
        return AsyncAzureOpenAI(
            azure_endpoint=self.base_url,
            api_key=self.api_key,
            api_version="2024-10-21",
            default_headers=self._extra_headers,
        )

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.2,
        headers: Optional[dict[str, str]] = None,
    ) -> ChatResponse:
        client = self._client()
        resp = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_headers=headers or {},
        )
        text = resp.choices[0].message.content or ""
        usage = resp.usage
        p_tok = getattr(usage, "prompt_tokens", 0) if usage else 0
        c_tok = getattr(usage, "completion_tokens", 0) if usage else 0
        return ChatResponse(
            text=text, prompt_tokens=p_tok, completion_tokens=c_tok,
            raw={"model": model, "via_apim": self.via_apim},
        )
