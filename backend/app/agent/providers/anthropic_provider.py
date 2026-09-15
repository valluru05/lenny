"""
agent/providers/anthropic_provider.py — Claude via the Anthropic SDK.

Uses the async client. Maps our CompletionRequest format to the
Anthropic messages API and normalises errors into ProviderError.
"""
from __future__ import annotations

from app.agent.providers.base import (
    CompletionRequest,
    CompletionResponse,
    LLMProvider,
    ProviderError,
)
from app.config import settings
from app.logging_conf import get_logger

log = get_logger("provider.anthropic")


class AnthropicProvider(LLMProvider):
    def __init__(self) -> None:
        if not settings.anthropic_api_key:
            raise ProviderError(
                "anthropic",
                "ANTHROPIC_API_KEY is not set",
                retryable=False,
            )
        # Lazy import — keeps startup fast if not configured
        import anthropic as _anthropic
        self._client = _anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._model = settings.anthropic_model

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def model(self) -> str:
        return self._model

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        # Anthropic separates system prompt from conversation messages
        system_prompt: str = ""
        messages: list[dict] = []

        for msg in request.messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            else:
                messages.append({"role": msg["role"], "content": msg["content"]})

        if not messages:
            raise ProviderError("anthropic", "No non-system messages provided")

        try:
            log.debug(
                "anthropic.request",
                model=self._model,
                messages=len(messages),
                max_tokens=request.max_tokens,
            )
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                system=system_prompt or "You are a helpful assistant.",
                messages=messages,
            )
            content = response.content[0].text
            log.debug(
                "anthropic.response",
                output_tokens=response.usage.output_tokens,
                input_tokens=response.usage.input_tokens,
            )
            return CompletionResponse(
                content=content,
                provider="anthropic",
                model=self._model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )
        except ProviderError:
            raise
        except Exception as exc:
            err_str = str(exc)
            retryable = any(
                kw in err_str.lower()
                for kw in ("timeout", "rate", "overload", "529", "503")
            )
            log.error("anthropic.error", exc=err_str)
            raise ProviderError("anthropic", err_str, retryable=retryable) from exc

    async def health_check(self) -> bool:
        """Use a minimal model call — cheapest available."""
        try:
            await self.complete(
                CompletionRequest(
                    messages=[{"role": "user", "content": "Hi"}],
                    max_tokens=1,
                    temperature=0.0,
                )
            )
            return True
        except ProviderError:
            return False
