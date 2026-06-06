"""Provider abstraction — base class + response dataclass.

Every backend (AOAI, Foundry, Databricks-Anthropic, Anthropic-direct) implements
the same `chat(...)` contract so stages.py is provider-agnostic. Per-stage
routing is config-driven (see config.STAGE_PROVIDERS); per-run overrides ride
on RunState.stage_provider_overrides.

Governance Plane note (design.md §1):
  Every provider carries a `via_apim` flag. When True, the call SHOULD traverse
  APIM_BASE_URL so the Policy Decision Point sees it. AOAI defaults to True
  (today's working path). Foundry/Databricks/Anthropic-direct default to False
  with a Phase 1 TODO — APIM passthrough policies for those backends are
  scaffolded but not yet fully configured (see docs/PROVIDERS.md#apim-config).
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

_logger = logging.getLogger("orchestrator.providers")


@dataclass
class ChatResponse:
    """Uniform response shape across providers — keeps stages.py decoupled."""
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


class Provider(ABC):
    """Base class for chat-completion providers.

    Subclasses set `name` for registry lookup and implement `chat`. The
    `via_apim` flag is read by the implementation to decide whether to point
    at APIM_BASE_URL or the backend's direct URL.
    """
    name: str = "base"

    def __init__(self, via_apim: bool = False) -> None:
        self.via_apim = via_apim
        if via_apim and self.name not in {"aoai"}:
            # Phase 1 honesty — APIM passthrough policy not yet wired for these backends.
            _logger.info(
                "provider=%s via_apim=True but APIM passthrough policy is Phase 1 "
                "scaffolding for this backend; see docs/PROVIDERS.md#apim-config",
                self.name,
            )

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.2,
        headers: Optional[dict[str, str]] = None,
    ) -> ChatResponse:
        """Execute one chat completion and return a uniform ChatResponse."""
        raise NotImplementedError
