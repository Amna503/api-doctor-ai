from __future__ import annotations

import asyncio
import time
from typing import Any

from ..config import Settings, settings
from .base import ModelCallResult


class GemmaAdapter:
    """Google AI Studio adapter for Gemma via the official google-genai SDK.

    The model identifier is configurable because Google's available model lineup
    changes. The default is verified against Google's current Gemma-on-Gemini-API
    documentation (gemma-4-26b-a4b-it). No key ever leaves the backend.
    """

    provider = "google-ai-studio"

    def __init__(self, config: Settings | None = None) -> None:
        self.config = config or settings
        self.model = self.config.gemma_model
        self._client: Any | None = None

    @property
    def enabled(self) -> bool:
        return self.config.gemma_enabled

    def _client_or_raise(self) -> Any:
        if not self.enabled:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        if self._client is None:
            from google import genai
            from google.genai import types

            timeout_ms = int(self.config.gemma_timeout_seconds * 1000)
            self._client = genai.Client(
                api_key=self.config.gemma_api_key,
                http_options=types.HttpOptions(timeout=timeout_ms),
            )
        return self._client

    async def generate_migration(self, prompt: str, prompt_version: str) -> ModelCallResult:
        started = time.perf_counter()
        errors: list[str] = []
        attempts_allowed = max(1, self.config.gemma_max_retries + 1)
        if not self.enabled:
            return ModelCallResult(
                raw_text=None,
                model=self.model,
                provider=self.provider,
                attempts=0,
                duration_ms=0,
                errors=["GEMINI_API_KEY is not configured on the backend"],
                status="disabled",
                prompt_version=prompt_version,
            )

        for attempt in range(1, attempts_allowed + 1):
            try:
                client = self._client_or_raise()
                from google.genai import types

                response = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=self.model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            temperature=0.2,
                            max_output_tokens=2400,
                        ),
                    ),
                    timeout=self.config.gemma_timeout_seconds,
                )
                text = getattr(response, "text", None)
                if not text or not str(text).strip():
                    raise RuntimeError("Gemma returned an empty response")
                return ModelCallResult(
                    raw_text=str(text),
                    model=self.model,
                    provider=self.provider,
                    attempts=attempt,
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    errors=errors,
                    status="success",
                    prompt_version=prompt_version,
                )
            except Exception as exc:  # network, auth, quota, malformed response
                errors.append(f"attempt {attempt}: {type(exc).__name__}: {str(exc)[:240]}")
                if attempt < attempts_allowed:
                    await asyncio.sleep(min(1.5, 0.4 * attempt))
        return ModelCallResult(
            raw_text=None,
            model=self.model,
            provider=self.provider,
            attempts=attempts_allowed,
            duration_ms=int((time.perf_counter() - started) * 1000),
            errors=errors,
            status="error",
            prompt_version=prompt_version,
        )
