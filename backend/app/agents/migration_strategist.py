from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..config import settings
from ..llm.base import ModelAdapter, ModelOutputError, extract_json_object
from ..llm.fallback import build_fallback_plan
from ..llm.gemma import GemmaAdapter
from ..llm.prompts import PROMPT_VERSION, build_migration_prompt
from ..models import Consumer, Finding, MigrationPlan, MigrationStep
from ..skills import Skill, load_skill


class MigrationStrategistInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    findings: list[Finding]
    consumers: list[Consumer] = Field(default_factory=list)
    old_meta: dict
    new_meta: dict
    new_endpoints: list[str] = Field(default_factory=list)


class RawStep(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str = Field(min_length=1, max_length=200)
    detail: str = Field(min_length=1, max_length=3000)
    finding_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.7, ge=0)
    code_before: str | None = None
    code_after: str | None = None
    notes: str | None = None


class RawPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")
    summary: str = Field(min_length=1, max_length=3000)
    strategy: str = Field(min_length=1, max_length=3000)
    steps: list[RawStep] = Field(min_length=1, max_length=20)


@dataclass
class MigrationStrategistOutput:
    plan: MigrationPlan
    trace_status: str
    trace_detail: str
    trace_error: str | None
    attempts: int
    provider: str
    model: str
    duration_ms: int


def _validate_model_plan(
    raw: dict,
    findings: list[Finding],
    model: str,
    errors: list[str],
    attempts: int,
) -> MigrationPlan:
    parsed = RawPlan.model_validate(raw)
    valid_ids = {finding.id for finding in findings}
    steps: list[MigrationStep] = []
    dropped = 0
    for index, step in enumerate(parsed.steps[:10], start=1):
        cited = [item for item in step.finding_ids if item in valid_ids]
        if not cited:
            dropped += 1
            continue
        steps.append(
            MigrationStep(
                id=f"MIG-{index:02d}",
                title=step.title[:200],
                detail=step.detail[:3000],
                finding_ids=sorted(set(cited)),
                confidence=round(min(1.0, max(0.0, step.confidence)), 2),
                code_before=(step.code_before or "")[:4000] or None,
                code_after=(step.code_after or "")[:4000] or None,
                notes=(step.notes or "")[:1000] or None,
            )
        )
    if not steps:
        raise ModelOutputError("Model returned no migration steps citing valid finding evidence")
    warnings = [
        "AI-generated suggestions from Gemma; deterministic findings are the source of truth.",
        "Verification results are reported separately by the sandbox. This plan is not a proof of compatibility.",
    ]
    if dropped:
        warnings.append(f"{dropped} model step(s) were discarded because they cited unknown evidence IDs.")
    if attempts > 1:
        warnings.append(f"Model succeeded after {attempts} attempt(s).")
    if errors:
        warnings.extend(errors[-2:])
    return MigrationPlan(
        source="gemma",
        model=model,
        prompt_version=PROMPT_VERSION,
        summary=parsed.summary[:3000],
        strategy=parsed.strategy[:3000],
        steps=steps,
        warnings=warnings,
        generated_at=datetime.now(timezone.utc),
    )


class MigrationStrategist:
    name = "Migration Strategist"
    responsibility = (
        "Use Gemma through the backend-only Google AI Studio adapter to turn deterministic findings into "
        "evidence-cited migration steps. Invalid, uncited, or unavailable model output is replaced by a "
        "clearly labelled deterministic fallback."
    )
    timeout_seconds = 45.0
    max_retries = settings.gemma_max_retries

    def __init__(self, adapter: ModelAdapter | None = None, skill: Skill | None = None) -> None:
        self.adapter = adapter or GemmaAdapter()
        self.skill = skill or load_skill()

    async def run(self, payload: MigrationStrategistInput) -> MigrationStrategistOutput:
        started = perf_counter()
        compact_findings = []
        for finding in payload.findings[:22]:
            compact_findings.append(
                {
                    "id": finding.id,
                    "rule": finding.rule,
                    "severity": finding.severity,
                    "breaking": finding.breaking,
                    "title": finding.title,
                    "detail": finding.detail[:500],
                    "method": finding.method,
                    "path": finding.path,
                    "location": finding.location,
                    "suggestion": finding.suggestion,
                }
            )
        consumers = [
            {"name": consumer.name, "owner": consumer.owner, "endpoints": consumer.endpoints}
            for consumer in payload.consumers[:20]
        ]
        prompt = build_migration_prompt(
            compact_findings,
            consumers,
            payload.old_meta,
            payload.new_meta,
            payload.new_endpoints[:80],
            skill_guidance=self.skill.body,
        )

        result = None
        error_text = None
        try:
            result = await self.adapter.generate_migration(prompt, PROMPT_VERSION)
        except Exception as exc:  # adapter must not crash the pipeline
            error_text = f"{type(exc).__name__}: {str(exc)[:300]}"

        if result is not None and result.raw_text:
            try:
                raw = extract_json_object(result.raw_text)
                plan = _validate_model_plan(
                    raw,
                    payload.findings,
                    result.model,
                    result.errors,
                    result.attempts,
                )
                duration_ms = int((perf_counter() - started) * 1000)
                detail = (
                    f"Gemma returned schema-valid guidance after {result.attempts} attempt(s). "
                    f"Provider latency: {result.duration_ms} ms. "
                    f"Applied skill {self.skill.name} v{self.skill.version}."
                )
                return MigrationStrategistOutput(
                    plan=plan,
                    trace_status="success",
                    trace_detail=detail + (" Warnings: " + "; ".join(result.errors[-2:]) if result.errors else ""),
                    trace_error=None,
                    attempts=result.attempts,
                    provider=result.provider,
                    model=result.model,
                    duration_ms=duration_ms,
                )
            except (ValidationError, ModelOutputError) as exc:
                error_text = f"output validation failed: {str(exc)[:300]}"
            except Exception as exc:
                error_text = f"{type(exc).__name__}: {str(exc)[:300]}"

        if result is not None and not result.raw_text and result.errors:
            error_text = "; ".join(result.errors[-2:])
        elif result is not None and result.status == "disabled" and result.errors:
            error_text = "; ".join(result.errors)

        reason = error_text or "model output unavailable"
        plan = build_fallback_plan(
            payload.findings,
            payload.consumers,
            payload.new_endpoints,
            model=self.adapter.model,
            prompt_version=PROMPT_VERSION,
            reason=reason[:300],
            generated_at=datetime.now(timezone.utc),
        )
        duration_ms = int((perf_counter() - started) * 1000)
        return MigrationStrategistOutput(
            plan=plan,
            trace_status="fallback",
            trace_detail=(
                "Gemma was not used. Deterministic fallback guidance was generated and labelled. "
                "No model output is being presented."
            ),
            trace_error=reason[:400],
            attempts=result.attempts if result else 0,
            provider=self.adapter.provider,
            model=self.adapter.model,
            duration_ms=duration_ms,
        )
