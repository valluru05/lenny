"""
agent/providers/ollama_provider.py — Local Ollama via httpx async.

Calls the /api/chat endpoint (OpenAI-compatible format).
Designed for the mandatory local-demo requirement — works fully
offline next to Ollama running on the same machine.

Failure modes handled:
  - Connection refused (Ollama not running)
  - Model not found (404)
  - Request timeout (model too slow / overloaded)
  - Any other HTTP/network error
"""
from __future__ import annotations

import httpx

from app.agent.providers.base import (
    CompletionRequest,
    CompletionResponse,
    LLMProvider,
    ProviderError,
)
from app.config import settings
from app.logging_conf import get_logger

log = get_logger("provider.ollama")


class OllamaProvider(LLMProvider):
    def __init__(self) -> None:
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._model = settings.ollama_model
        self._timeout = settings.ollama_timeout

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def model(self) -> str:
        return self._model

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        payload = {
            "model": self._model,
            "messages": request.messages,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }

        try:
            log.debug(
                "ollama.request",
                model=self._model,
                messages=len(request.messages),
                timeout=self._timeout,
            )
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/api/chat",
                    json=payload,
                )

            if resp.status_code == 404:
                raise ProviderError(
                    "ollama",
                    f"Model '{self._model}' not found. "
                    f"Run: ollama pull {self._model}",
                    retryable=False,
                )
            if resp.status_code != 200:
                raise ProviderError(
                    "ollama",
                    f"HTTP {resp.status_code}: {resp.text[:200]}",
                    retryable=resp.status_code >= 500,
                )

            data = resp.json()
            content = data.get("message", {}).get("content", "")
            if not content:
                raise ProviderError("ollama", "Empty response from model")

            log.debug("ollama.response", chars=len(content))
            return CompletionResponse(
                content=content,
                provider="ollama",
                model=self._model,
            )

        except ProviderError:
            raise
        except httpx.ConnectError as exc:
            raise ProviderError(
                "ollama",
                f"Cannot reach Ollama at {self._base_url}. "
                "Is Ollama running? (ollama serve)",
                retryable=True,
            ) from exc
        except httpx.TimeoutException as exc:
            raise ProviderError(
                "ollama",
                f"Request timed out after {self._timeout}s. "
                "Try a smaller model or increase OLLAMA_TIMEOUT.",
                retryable=True,
            ) from exc
        except Exception as exc:
            log.error("ollama.error", exc=str(exc))
            raise ProviderError("ollama", str(exc), retryable=False) from exc

    async def health_check(self) -> bool:
        """Ping /api/tags — cheaper than a full completion."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{self._base_url}/api/tags")
            return resp.status_code == 200
        except Exception:
            return False
