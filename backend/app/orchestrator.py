from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

from .agents.contract_analyzer import ContractAnalyzer, ContractAnalyzerInput
from .agents.impact_mapper import (
    ImpactMapper,
    ImpactMapperDependencies,
    ImpactMapperInput,
)
from .agents.migration_strategist import MigrationStrategist, MigrationStrategistInput
from .agents.test_engineer import EngineerInput, TestEngineer
from .agents.verification import (
    VerificationAgent,
    VerificationInput,
    assess_risk,
)
from .analysis.differ import diff_specs
from .analysis.loader import LoadedSpec, load_spec
from .config import settings
from .models import (
    AnalysisResult,
    AnalyzeRequest,
    Finding,
    MigrationPlan,
    RiskAssessment,
    SpecMeta,
    Summary,
    TestStatus,
    VerificationResult,
    VerifyRequest,
)
from .sandbox.patch import build_compatibility_patch


def _analysis_id(request: AnalyzeRequest) -> str:
    payload = {
        "old": request.old_spec,
        "new": request.new_spec,
        "consumers": [consumer.model_dump() for consumer in request.consumers],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return "AD-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12].upper()


def _spec_meta(loaded: LoadedSpec) -> SpecMeta:
    return SpecMeta(**loaded.meta())


def _summary(
    analysis_id: str,
    old: LoadedSpec,
    new: LoadedSpec,
    findings: list[Finding],
    endpoints_added: int,
    endpoints_removed: int,
    operations_affected: int,
) -> Summary:
    by_severity: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for finding in findings:
        by_severity[finding.severity] = by_severity.get(finding.severity, 0) + 1
    breaking = sum(1 for finding in findings if finding.breaking)
    return Summary(
        analysis_id=analysis_id,
        breaking_changes=breaking,
        non_breaking_changes=len(findings) - breaking,
        total_changes=len(findings),
        by_severity=by_severity,
        endpoints_added=endpoints_added,
        endpoints_removed=endpoints_removed,
        operations_affected=operations_affected,
        old_endpoint_count=len(old.operations),
        new_endpoint_count=len(new.operations),
    )


class Orchestrator:
    def __init__(self) -> None:
        self.contract_analyzer = ContractAnalyzer()
        self.impact_mapper = ImpactMapper()
        self.migration_strategist = MigrationStrategist()
        self.test_engineer = TestEngineer()
        self.verification_agent = VerificationAgent()

    async def analyze(self, request: AnalyzeRequest, recorder) -> AnalysisResult:
        started_at = datetime.now(timezone.utc)
        contract, duration = self._timed(
            self.contract_analyzer.run,
            ContractAnalyzerInput(
                old_spec=request.old_spec,
                new_spec=request.new_spec,
                max_findings=settings.max_findings,
            ),
        )
        recorder.record(
            agent=self.contract_analyzer.name,
            action="Deterministic contract diff",
            status="success",
            started_at=started_at,
            duration_ms=duration,
            detail=f"{len(contract.findings)} findings from {len(contract.old.operations)} -> {len(contract.new.operations)} operations",
            evidence_count=len(contract.findings),
        )

        started_at = datetime.now(timezone.utc)
        impact, duration = self._timed(
            self.impact_mapper.run,
            ImpactMapperInput(
                consumers=request.consumers,
                finding_count=len(contract.findings),
            ),
            ImpactMapperDependencies(
                old=contract.old,
                new=contract.new,
                findings=contract.findings,
            ),
        )
        recorder.record(
            agent=self.impact_mapper.name,
            action="Map endpoints and declared consumers",
            status="success",
            started_at=started_at,
            duration_ms=duration,
            detail=(
                f"{len(impact.impact.affected_endpoints)} affected endpoints, "
                f"{impact.affected_consumer_count} affected consumers"
            ),
            evidence_count=len(impact.impact.affected_endpoints),
        )

        started_at = datetime.now(timezone.utc)
        migration_result = await self.migration_strategist.run(
            MigrationStrategistInput(
                findings=contract.findings,
                consumers=request.consumers,
                old_meta=contract.old.meta(),
                new_meta=contract.new.meta(),
                new_endpoints=contract.new.endpoint_keys,
            )
        )
        plan: MigrationPlan = migration_result.plan
        recorder.record(
            agent=self.migration_strategist.name,
            action="Generate evidence-cited migration guidance",
            status="success" if migration_result.trace_status == "success" else "fallback",
            started_at=started_at,
            duration_ms=migration_result.duration_ms,
            attempt=migration_result.attempts or 1,
            provider=migration_result.provider,
            model=migration_result.model,
            prompt_version=plan.prompt_version,
            detail=migration_result.trace_detail,
            error=migration_result.trace_error,
            evidence_count=len(contract.findings),
        )

        started_at = datetime.now(timezone.utc)
        tests, duration = self._timed(
            self.test_engineer.run,
            EngineerInput(
                findings=contract.findings,
                max_tests=settings.max_tests,
            ),
            contract.old,
            contract.new,
        )
        recorder.record(
            agent=self.test_engineer.name,
            action="Generate bounded regression checks",
            status="success",
            started_at=started_at,
            duration_ms=duration,
            detail=f"{len(tests.tests)} checks generated for the structured sandbox",
            evidence_count=len(tests.tests),
        )

        risk = assess_risk(
            contract.findings,
            tests.tests,
            [],
            verified=False,
        )
        started_at = datetime.now(timezone.utc)
        recorder.record(
            agent=self.verification_agent.name,
            action="Pre-verification risk assessment",
            status="skipped",
            started_at=started_at,
            duration_ms=0,
            detail="Verification not executed yet; no compatibility claim is made.",
            evidence_count=risk.unresolved_findings,
        )

        analysis_id = _analysis_id(request)
        return AnalysisResult(
            analysis_id=analysis_id,
            generated_at=datetime.now(timezone.utc),
            old_spec=_spec_meta(contract.old),
            new_spec=_spec_meta(contract.new),
            summary=_summary(
                analysis_id,
                contract.old,
                contract.new,
                contract.findings,
                contract.endpoints_added,
                contract.endpoints_removed,
                contract.operations_affected,
            ),
            findings=contract.findings,
            impact=impact.impact,
            migration=plan,
            tests=tests,
            risk=risk,
            traces=recorder.traces,
            disclaimer=(
                "Deterministic rules produce findings. Gemma produces suggestions only. "
                "Verification results are actual sandbox outputs and never fabricated."
            ),
        )

    async def verify(self, request: VerifyRequest, recorder) -> VerificationResult:
        started_all = datetime.now(timezone.utc)
        run_started = datetime.now(timezone.utc)
        contract, duration = self._timed(
            self.contract_analyzer.run,
            ContractAnalyzerInput(
                old_spec=request.old_spec,
                new_spec=request.new_spec,
                max_findings=settings.max_findings,
            ),
        )
        recorder.record(
            agent=self.contract_analyzer.name,
            action="Revalidate contracts before verification",
            status="success",
            started_at=run_started,
            duration_ms=duration,
            detail=f"{len(contract.findings)} findings",
            evidence_count=len(contract.findings),
        )

        target_new = contract.new
        effective_findings = contract.findings
        patch = None
        patch_applied = False
        original_breaking = sum(1 for finding in contract.findings if finding.breaking)

        if request.apply_compatibility_patch:
            run_started = datetime.now(timezone.utc)
            patched_raw, patch = build_compatibility_patch(contract.old, contract.new, contract.findings)
            patched_new = load_spec(patched_raw, "patched specification")
            residual = diff_specs(contract.old, patched_new, max_findings=settings.max_findings)
            patch = patch.model_copy(
                update={
                    "residual_breaking_changes": sum(1 for item in residual if item.breaking),
                    "residual_findings": [
                        f"{item.id} {item.title}" for item in residual if item.breaking
                    ][:12],
                }
            )
            target_new = patched_new
            effective_findings = residual
            patch_applied = True
            recorder.record(
                agent=self.verification_agent.name,
                action="Apply simulated compatibility shim",
                status="success",
                started_at=run_started,
                duration_ms=int((datetime.now(timezone.utc) - run_started).total_seconds() * 1000),
                detail=(
                    f"{len(patch.changes)} shim change(s); {len(patch.remaining_unpatchable)} unpatchable item(s); "
                    f"{patch.residual_breaking_changes} residual breaking finding(s)"
                ),
                evidence_count=len(patch.changes),
            )

        run_started = datetime.now(timezone.utc)
        tests, duration = self._timed(
            self.test_engineer.run,
            EngineerInput(
                findings=contract.findings,
                max_tests=settings.max_tests,
            ),
            contract.old,
            target_new,
        )
        recorder.record(
            agent=self.test_engineer.name,
            action="Regenerate regression checks against target contract",
            status="success",
            started_at=run_started,
            duration_ms=duration,
            detail=f"{len(tests.tests)} checks",
            evidence_count=len(tests.tests),
        )

        run_started = datetime.now(timezone.utc)
        verification, duration = self._timed(
            self.verification_agent.run,
            VerificationInput(tests=tests.tests, budget_ms=settings.sandbox_budget_ms),
            contract.old,
            target_new,
        )
        recorder.record(
            agent=self.verification_agent.name,
            action="Execute bounded checks in isolated sandbox",
            status="success",
            started_at=run_started,
            duration_ms=verification.duration_ms,
            detail=(
                f"{len(verification.results)} executed, "
                f"{len([item for item in verification.results if item.status == 'failed'])} failed, "
                f"{verification.skipped} skipped in structured sandbox"
            ),
            evidence_count=len(verification.results),
        )

        risk = assess_risk(
            effective_findings,
            tests.tests,
            verification.results,
            verified=True,
            original_breaking_count=original_breaking,
            patch_applied=patch_applied,
        )
        run_started = datetime.now(timezone.utc)
        recorder.record(
            agent=self.verification_agent.name,
            action="Compute residual risk from actual results",
            status="success",
            started_at=run_started,
            duration_ms=0,
            detail=risk.summary,
            evidence_count=len(verification.results),
        )

        passed = len([item for item in verification.results if item.status == "passed"])
        failed = len([item for item in verification.results if item.status == "failed"])
        skipped = len([item for item in verification.results if item.status == "skipped"])
        return VerificationResult(
            analysis_id=_analysis_id(request),
            run_id="RUN-" + uuid.uuid4().hex[:10].upper(),
            executed_at=datetime.now(timezone.utc),
            duration_ms=int((datetime.now(timezone.utc) - started_all).total_seconds() * 1000),
            sandbox="api-doctor-sandbox/v1 (in-process, allow-listed structured checks)",
            sandbox_notes=(
                "No generated code is executed. Checks only read the two in-memory OpenAPI documents and "
                "validate synthesized payloads with JSON Schema. No network, filesystem, shell, or secrets access. "
                f"Total budget: {settings.sandbox_budget_ms} ms; max {settings.max_tests} checks."
            ),
            total=len(verification.results),
            passed=passed,
            failed=failed,
            skipped=skipped,
            results=verification.results,
            risk=risk,
            compatibility_patch=patch,
            traces=recorder.traces,
        )

    @staticmethod
    def _timed(function, *args):
        from time import perf_counter

        started = perf_counter()
        result = function(*args)
        return result, int((perf_counter() - started) * 1000)
