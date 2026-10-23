from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from ..models import ExecutionTrace, TraceStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AgentError(RuntimeError):
    pass


class TraceRecorder:
    def __init__(self) -> None:
        self.traces: list[ExecutionTrace] = []

    def record(
        self,
        *,
        agent: str,
        action: str,
        status: TraceStatus,
        started_at: datetime,
        duration_ms: int,
        attempt: int = 1,
        provider: str | None = None,
        model: str | None = None,
        prompt_version: str | None = None,
        detail: str | None = None,
        error: str | None = None,
        evidence_count: int | None = None,
    ) -> ExecutionTrace:
        trace = ExecutionTrace(
            agent=agent,
            action=action,
            status=status,
            started_at=started_at,
            duration_ms=max(0, duration_ms),
            attempt=attempt,
            provider=provider,
            model=model,
            prompt_version=prompt_version,
            detail=detail,
            error=error,
            evidence_count=evidence_count,
        )
        self.traces.append(trace)
        return trace


class BaseAgent(ABC):
    """A bounded, typed agent module.

    Each subclass declares its responsibility, a hard timeout, and a bounded
    retry budget. Retries are only used by agents that call an unreliable
    external dependency (the model).
    """

    name: str
    responsibility: str
    timeout_seconds: float = 10.0
    max_retries: int = 0

    @abstractmethod
    def run(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError

    async def run_async(self, *args: Any, **kwargs: Any) -> Any:
        return await asyncio.wait_for(
            asyncio.to_thread(self.run, *args, **kwargs),
            timeout=self.timeout_seconds,
        )

    def timed(self, callable_: Any, *args: Any, **kwargs: Any) -> tuple[Any, int]:
        started = perf_counter()
        result = callable_(*args, **kwargs)
        return result, int((perf_counter() - started) * 1000)
