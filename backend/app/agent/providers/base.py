"""
agent/providers/base.py — LLMProvider interface.

All providers implement this contract. The orchestrator and skills
only ever talk to this interface — swapping the underlying model
requires only changing LLM_PROVIDER in the environment, never
touching application code.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


class ProviderError(Exception):
    """
    Raised when a provider cannot complete a request.
    Carries enough context for a structured 503 response — never
    an unhandled stack trace to the user.
    """
    def __init__(self, provider: str, reason: str, retryable: bool = False) -> None:
        self.provider = provider
        self.reason = reason
        self.retryable = retryable
        super().__init__(f"[{provider}] {reason}")


@dataclass
class CompletionRequest:
    """Structured input to any provider."""
    messages: list[dict]          # OpenAI-style: [{"role": "user"|"assistant"|"system", "content": str}]
    max_tokens: int = 4096
    temperature: float = 0.7


@dataclass
class CompletionResponse:
    """Structured output from any provider."""
    content: str                  # The model's text response
    provider: str                 # Which provider produced this
    model: str                    # Which model was used
    used_fallback: bool = False   # True if the primary provider failed
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


class LLMProvider(ABC):
    """Abstract base for all LLM provider implementations."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier string (e.g. 'anthropic', 'ollama', 'mock')."""
        ...

    @property
    @abstractmethod
    def model(self) -> str:
        """Model identifier string."""
        ...

    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """
        Send messages to the model and return its response.
        Must raise ProviderError on any failure — never let raw
        SDK/HTTP exceptions propagate to the orchestrator.
        """
        ...

    async def health_check(self) -> bool:
        """
        Quick reachability check.  Returns True if provider is usable.
        Default implementation tries a minimal completion.
        Override in providers that have a cheaper ping endpoint.
        """
        try:
            await self.complete(
                CompletionRequest(
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=1,
                )
            )
            return True
        except ProviderError:
            return False
