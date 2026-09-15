"""
agent/router.py — LLMRouter: provider selection + fallback.

Architecture decision (documented in architecture.md):
  We implement a custom lightweight orchestrator rather than using the
  Claude Agent SDK or Pi Coding Agent. Both are built around the Claude
  Code CLI runtime and assume Claude as the model, which conflicts with
  the mandatory local-Ollama-for-the-demo requirement. This router mirrors
  the same core pattern those SDKs use — primary provider, optional fallback,
  structured error on total failure — without binding to a specific provider.

Fallback behavior:
  1. Try primary provider (LLM_PROVIDER).
  2. If ProviderError and LLM_FALLBACK_PROVIDER is set → try fallback.
  3. If fallback also fails (or none configured) → raise AllProvidersError.
  The chat API catches AllProvidersError and returns a structured 503.
  The UI shows the error clearly — never an unhandled exception.
"""
from __future__ import annotations

from typing import Optional

from app.agent.providers.base import (
    CompletionRequest,
    CompletionResponse,
    LLMProvider,
    ProviderError,
)
from app.config import settings
from app.logging_conf import get_logger

log = get_logger("agent.router")


class AllProvidersError(Exception):
    """Raised when both primary and fallback providers fail."""
    def __init__(self, primary_err: str, fallback_err: Optional[str] = None) -> None:
        self.primary_err = primary_err
        self.fallback_err = fallback_err
        msg = f"Primary provider failed: {primary_err}"
        if fallback_err:
            msg += f" | Fallback also failed: {fallback_err}"
        super().__init__(msg)


def _build_provider(name: str) -> LLMProvider:
    """Instantiate a provider by name. Raises ProviderError if misconfigured."""
    if name == "anthropic":
        from app.agent.providers.anthropic_provider import AnthropicProvider
        return AnthropicProvider()
    if name == "ollama":
        from app.agent.providers.ollama_provider import OllamaProvider
        return OllamaProvider()
    if name == "mock":
        from app.agent.providers.mock_provider import MockProvider
        return MockProvider()
    raise ProviderError("router", f"Unknown provider name: '{name}'")


class LLMRouter:
    """
    Selects and calls the configured LLM provider with fallback.

    Usage:
        router = LLMRouter()
        response = await router.complete(request)
        # response.used_fallback tells you which path was taken
    """

    def __init__(
        self,
        primary_name: Optional[str] = None,
        fallback_name: Optional[str] = None,
    ) -> None:
        self._primary_name = primary_name or settings.llm_provider
        self._fallback_name = fallback_name or settings.llm_fallback_provider
        self._primary: Optional[LLMProvider] = None
        self._fallback: Optional[LLMProvider] = None

    def _get_primary(self) -> LLMProvider:
        if self._primary is None:
            self._primary = _build_provider(self._primary_name)
        return self._primary

    def _get_fallback(self) -> Optional[LLMProvider]:
        if not self._fallback_name:
            return None
        if self._fallback is None:
            try:
                self._fallback = _build_provider(self._fallback_name)
            except ProviderError as exc:
                log.warning("router.fallback_init_failed", exc=str(exc))
                return None
        return self._fallback

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """
        Try primary → fallback → AllProvidersError.
        Sets response.used_fallback=True if fallback was used.
        """
        primary_err: Optional[str] = None

        # ── Primary ──────────────────────────────────────────────────────────
        try:
            provider = self._get_primary()
            log.debug("router.trying_primary", provider=provider.name, model=provider.model)
            response = await provider.complete(request)
            log.info(
                "router.success",
                provider=response.provider,
                model=response.model,
                used_fallback=False,
            )
            return response
        except ProviderError as exc:
            primary_err = str(exc)
            log.warning(
                "router.primary_failed",
                provider=self._primary_name,
                exc=primary_err,
                has_fallback=bool(self._fallback_name),
            )

        # ── Fallback ─────────────────────────────────────────────────────────
        fallback = self._get_fallback()
        if fallback is None:
            raise AllProvidersError(primary_err=primary_err)

        try:
            log.info(
                "router.trying_fallback",
                provider=fallback.name,
                model=fallback.model,
            )
            response = await fallback.complete(request)
            response.used_fallback = True
            log.info(
                "router.fallback_success",
                provider=response.provider,
                model=response.model,
            )
            return response
        except ProviderError as exc:
            fallback_err = str(exc)
            log.error(
                "router.fallback_failed",
                provider=self._fallback_name,
                exc=fallback_err,
            )
            raise AllProvidersError(
                primary_err=primary_err,
                fallback_err=fallback_err,
            )

    @property
    def primary_name(self) -> str:
        return self._primary_name

    @property
    def fallback_name(self) -> Optional[str]:
        return self._fallback_name
