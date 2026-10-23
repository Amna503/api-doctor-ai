from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ModelCallResult:
    raw_text: str | None
    model: str
    provider: str
    attempts: int
    duration_ms: int
    errors: list[str] = field(default_factory=list)
    status: str = "success"
    prompt_version: str = ""


class ModelAdapter(Protocol):
    provider: str
    model: str

    @property
    def enabled(self) -> bool: ...

    async def generate_migration(self, prompt: str, prompt_version: str) -> ModelCallResult: ...


class ModelUnavailableError(RuntimeError):
    pass


class ModelOutputError(RuntimeError):
    pass


def extract_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end < start:
        raise ModelOutputError("Model output did not contain a JSON object")
    import json

    try:
        value = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ModelOutputError(f"Model output was not valid JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ModelOutputError("Model output JSON must be an object")
    return value
