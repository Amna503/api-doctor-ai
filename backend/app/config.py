from __future__ import annotations

import os
from dataclasses import dataclass, field


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_name: str = "API Doctor AI"
    app_version: str = "1.0.0"
    environment: str = field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    gemma_model: str = field(
        default_factory=lambda: os.getenv("GEMMA_MODEL", "gemma-4-26b-a4b-it")
    )
    gemma_api_key: str = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))
    )
    gemma_timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("GEMMA_TIMEOUT_SECONDS", "25"))
    )
    gemma_max_retries: int = field(
        default_factory=lambda: _int_env("GEMMA_MAX_RETRIES", 2)
    )
    max_body_bytes: int = field(
        default_factory=lambda: _int_env("MAX_BODY_BYTES", 2 * 1024 * 1024)
    )
    max_spec_paths: int = field(
        default_factory=lambda: _int_env("MAX_SPEC_PATHS", 300)
    )
    max_findings: int = field(
        default_factory=lambda: _int_env("MAX_FINDINGS", 250)
    )
    max_tests: int = field(default_factory=lambda: _int_env("MAX_TESTS", 24))
    sandbox_budget_ms: int = field(
        default_factory=lambda: _int_env("SANDBOX_BUDGET_MS", 5000)
    )
    cors_origins_raw: str = field(
        default_factory=lambda: os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        )
    )
    cors_origin_regex: str = field(
        default_factory=lambda: os.getenv("CORS_ORIGIN_REGEX", "")
    )

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins_raw.split(",") if item.strip()]

    @property
    def gemma_enabled(self) -> bool:
        return bool(self.gemma_api_key.strip())

    @property
    def prompt_version(self) -> str:
        return "migration-v1.3.0"


settings = Settings()
