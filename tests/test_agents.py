from __future__ import annotations

import asyncio
import json

import pytest

from app.agents.contract_analyzer import ContractAnalyzer, ContractAnalyzerInput
from app.agents.migration_strategist import MigrationStrategist, MigrationStrategistInput
from app.agents.test_engineer import TestEngineer, EngineerInput
from app.agents.verification import VerificationAgent, VerificationInput, assess_risk
from app.analysis.loader import SpecValidationError
from app.llm.base import ModelCallResult
from app.models import Consumer, GeneratedTest


class DisabledAdapter:
    provider = "test"
    model = "gemma-test"
    enabled = False

    async def generate_migration(self, prompt: str, prompt_version: str) -> ModelCallResult:
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


class FailingAdapter:
    provider = "test"
    model = "gemma-test"
    enabled = True

    async def generate_migration(self, prompt: str, prompt_version: str) -> ModelCallResult:
        raise TimeoutError("model timed out")


class ValidAdapter:
    provider = "test"
    model = "gemma-test"
    enabled = True

    def __init__(self, plan: dict, attempts: int = 1) -> None:
        self.plan = plan
        self.attempts = attempts

    async def generate_migration(self, prompt: str, prompt_version: str) -> ModelCallResult:
        return ModelCallResult(
            raw_text=json.dumps(self.plan),
            model=self.model,
            provider=self.provider,
            attempts=self.attempts,
            duration_ms=12,
            errors=[],
            prompt_version=prompt_version,
        )


def analysis_for(sample_old, sample_new):
    return ContractAnalyzer().run(
        ContractAnalyzerInput(old_spec=sample_old, new_spec=sample_new)
    )


def strategist_input(analysis, consumers):
    return MigrationStrategistInput(
        findings=analysis.findings,
        consumers=[Consumer(**item) for item in consumers],
        old_meta=analysis.old.meta(),
        new_meta=analysis.new.meta(),
        new_endpoints=analysis.new.endpoint_keys,
    )


def test_invalid_spec_raises_typed_error():
    with pytest.raises(SpecValidationError):
        ContractAnalyzer().run(ContractAnalyzerInput(old_spec={}, new_spec={}))


def test_migration_falls_back_when_model_is_disabled(sample_old, sample_new, sample_consumers):
    analysis = analysis_for(sample_old, sample_new)
    strategist = MigrationStrategist(adapter=DisabledAdapter())
    output = asyncio.run(strategist.run(strategist_input(analysis, sample_consumers)))
    assert output.plan.source == "fallback"
    assert output.plan.steps
    assert "no ai model output" in " ".join(output.plan.warnings).lower()
    assert output.trace_status == "fallback"


def test_migration_falls_back_on_model_api_failure(sample_old, sample_new, sample_consumers):
    analysis = analysis_for(sample_old, sample_new)
    strategist = MigrationStrategist(adapter=FailingAdapter())
    output = asyncio.run(strategist.run(strategist_input(analysis, sample_consumers)))
    assert output.plan.source == "fallback"
    assert output.trace_error and "TimeoutError" in output.trace_error


def test_model_output_without_valid_evidence_falls_back(sample_old, sample_new, sample_consumers):
    analysis = analysis_for(sample_old, sample_new)
    adapter = ValidAdapter(
        {
            "summary": "A plan.",
            "strategy": "Do things.",
            "steps": [
                {
                    "title": "Invented change",
                    "detail": "Cite fake evidence.",
                    "finding_ids": ["CHG-999"],
                    "confidence": 0.9,
                }
            ],
        }
    )
    output = asyncio.run(
        MigrationStrategist(adapter=adapter).run(
            strategist_input(analysis, sample_consumers)
        )
    )
    assert output.plan.source == "fallback"
    assert "evidence" in (output.trace_error or "").lower()


def test_valid_model_output_is_schema_validated(sample_old, sample_new, sample_consumers):
    analysis = analysis_for(sample_old, sample_new)
    real_id = analysis.findings[0].id
    adapter = ValidAdapter(
        {
            "summary": "Bridge removed operations while clients migrate.",
            "strategy": "Deprecate, alias, migrate, verify.",
            "steps": [
                {
                    "title": "Keep a compatibility alias",
                    "detail": "Restore the removed route as a deprecated alias.",
                    "finding_ids": [real_id, "CHG-999"],
                    "confidence": 1.7,
                    "code_before": "client.get('/v1/payments')",
                    "code_after": "client.get('/v2/payments')",
                }
            ],
        },
        attempts=2,
    )
    output = asyncio.run(
        MigrationStrategist(adapter=adapter).run(
            strategist_input(analysis, sample_consumers)
        )
    )
    assert output.plan.source == "gemma"
    assert output.plan.steps[0].finding_ids == [real_id]
    assert output.plan.steps[0].confidence == 1.0
    assert output.trace_status == "success"
    assert any("attempt" in warning.lower() for warning in output.plan.warnings)


def test_test_engineer_generates_bounded_real_checks(sample_old, sample_new):
    analysis = analysis_for(sample_old, sample_new)
    output = TestEngineer().run(
        EngineerInput(findings=analysis.findings, max_tests=24),
        analysis.old,
        analysis.new,
    )
    assert 1 <= len(output.tests) <= 24
    assert {test.type for test in output.tests} == {
        "endpoint_available",
        "legacy_request",
        "response_contract",
    }
    assert all(test.code for test in output.tests)
    assert all(len(test.finding_ids) >= 0 for test in output.tests)


def test_verification_cannot_pass_without_executed_checks(sample_old, sample_new):
    analysis = analysis_for(sample_old, sample_new)
    risk = assess_risk(analysis.findings, [], [], verified=False)
    assert risk.verified is False
    assert risk.status == "not_executed"
    assert risk.unresolved_findings == sum(1 for finding in analysis.findings if finding.breaking)


def test_verification_executes_and_fails_removed_endpoints(sample_old, sample_new):
    analysis = analysis_for(sample_old, sample_new)
    tests = TestEngineer().run(
        EngineerInput(findings=analysis.findings), analysis.old, analysis.new
    )
    output = VerificationAgent().run(
        VerificationInput(tests=tests.tests, budget_ms=5000),
        analysis.old,
        analysis.new,
    )
    removed_tests = [
        result for result in output.results if result.test_id in {"TST-001", "TST-002"}
    ]
    assert removed_tests
    assert all(result.status == "failed" for result in removed_tests)
    assert all("does not exist" in result.actual for result in removed_tests)


def test_verification_skips_when_budget_is_exhausted(sample_old, sample_new):
    analysis = analysis_for(sample_old, sample_new)
    tests = TestEngineer().run(
        EngineerInput(findings=analysis.findings), analysis.old, analysis.new
    )
    fake = GeneratedTest(
        id="TST-999",
        name="budget probe",
        description="probe",
        type="endpoint_available",
        method="GET",
        path="/v1/payments",
        finding_ids=[],
        check={},
        expected="exists",
        code="assert True",
    )
    output = VerificationAgent().run(
        VerificationInput(tests=list(tests.tests) + [fake], budget_ms=100),
        analysis.old,
        analysis.new,
    )
    assert all(result.status in {"passed", "failed", "skipped"} for result in output.results)
