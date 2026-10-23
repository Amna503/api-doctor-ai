from __future__ import annotations

from time import perf_counter

from pydantic import BaseModel, ConfigDict, Field

from ..analysis.differ import SEVERITY_WEIGHT
from ..analysis.loader import LoadedSpec
from ..models import (
    Finding,
    GeneratedTest,
    RiskAssessment,
    TestResult,
)
from ..sandbox.engine import execute_test
from .base import BaseAgent


class VerificationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tests: list[GeneratedTest]
    budget_ms: int = Field(default=5000, ge=100, le=20000)


class VerificationOutput(BaseModel):
    results: list[TestResult]
    duration_ms: int
    skipped: int


class VerificationAgent(BaseAgent):
    name = "Verification & Risk Agent"
    responsibility = (
        "Execute bounded structured contract checks in an isolated in-process sandbox, record actual "
        "pass/fail evidence, and compute residual risk. It never reports a pass unless a check actually ran."
    )
    timeout_seconds = 15.0
    max_retries = 0

    def run(
        self, payload: VerificationInput, old: LoadedSpec, new: LoadedSpec
    ) -> VerificationOutput:
        started = perf_counter()
        results: list[TestResult] = []
        for test in payload.tests:
            elapsed_ms = (perf_counter() - started) * 1000
            if elapsed_ms > payload.budget_ms:
                results.append(
                    TestResult(
                        test_id=test.id,
                        name=test.name,
                        type=test.type,
                        method=test.method,
                        path=test.path,
                        finding_ids=test.finding_ids,
                        status="skipped",
                        expected=test.expected,
                        actual="Skipped: sandbox execution budget exhausted.",
                        evidence=["sandbox-budget-exhausted"],
                        duration_ms=0,
                    )
                )
                continue
            results.append(execute_test(test, old, new))
        duration_ms = int((perf_counter() - started) * 1000)
        return VerificationOutput(
            results=results,
            duration_ms=duration_ms,
            skipped=len([item for item in results if item.status == "skipped"]),
        )


def _level(score: int) -> str:
    if score >= 70:
        return "critical"
    if score >= 45:
        return "high"
    if score >= 20:
        return "medium"
    if score > 0:
        return "low"
    return "clean"


def _unique_breaking(findings: list[Finding]) -> list[Finding]:
    seen: set[str] = set()
    out: list[Finding] = []
    for finding in findings:
        if finding.breaking and finding.id not in seen:
            seen.add(finding.id)
            out.append(finding)
    return out


def assess_risk(
    findings: list[Finding],
    tests: list[GeneratedTest],
    results: list[TestResult],
    *,
    verified: bool,
    original_breaking_count: int | None = None,
    patch_applied: bool = False,
) -> RiskAssessment:
    breaking = _unique_breaking(findings)
    failed = [item for item in results if item.status == "failed"]
    passed = [item for item in results if item.status == "passed"]
    skipped = [item for item in results if item.status == "skipped"]

    if not verified:
        unresolved = breaking
        score = min(100, sum(SEVERITY_WEIGHT[item.severity] for item in unresolved))
        return RiskAssessment(
            score=score,
            level=_level(score),  # type: ignore[arg-type]
            verified=False,
            status="not_executed",
            unresolved_findings=len(unresolved),
            resolved_findings=0,
            summary=(
                f"Deterministic pre-check only: {len(breaking)} breaking findings require verification. "
                "No regression checks have been executed."
            ),
            unresolved=[f"{item.id} {item.title}" for item in unresolved[:12]],
            evidence_coverage=0.0,
        )

    covered_ids: set[str] = set()
    for result in passed:
        covered_ids.update(result.finding_ids)
    failed_ids: set[str] = set()
    for result in failed:
        failed_ids.update(result.finding_ids)

    if patch_applied:
        unresolved = breaking
        original = original_breaking_count or len(breaking)
        resolved_count = max(0, original - len(breaking))
    else:
        unverified = [item for item in breaking if item.id not in covered_ids]
        unresolved_map: dict[str, Finding] = {item.id: item for item in breaking if item.id in failed_ids}
        for item in unverified:
            unresolved_map[item.id] = item
        unresolved = list(unresolved_map.values())
        resolved_count = len(breaking) - len(unresolved)

    score = min(
        100,
        sum(SEVERITY_WEIGHT[item.severity] for item in unresolved)
        + (5 * len(failed))
        + (2 if skipped else 0),
    )
    if failed or unresolved:
        status = "unresolved_risks"
        summary = (
            f"Executed {len(results)} sandbox checks: {len(passed)} passed, {len(failed)} failed, "
            f"{len(skipped)} skipped. {len(unresolved)} breaking finding(s) remain unresolved."
        )
    else:
        status = "verified_compatible"
        summary = (
            f"Executed {len(results)} sandbox checks: {len(passed)} passed, 0 failed. "
            "Legacy contract behavior is verified against the target specification by the executed checks."
        )
    if patch_applied and unresolved:
        summary += (
            f" Compatibility shim reduced breaking findings from {original_breaking_count} to "
            f"{len(breaking)}; remaining issues need real code or contract changes."
        )

    total_tests = max(1, len(tests))
    coverage = min(1.0, len(passed) / total_tests)
    return RiskAssessment(
        score=score,
        level=_level(score),  # type: ignore[arg-type]
        verified=True,
        status=status,  # type: ignore[arg-type]
        unresolved_findings=len(unresolved),
        resolved_findings=resolved_count,
        summary=summary,
        unresolved=[f"{item.id} {item.title} ({item.location})" for item in unresolved[:12]],
        evidence_coverage=round(coverage, 3),
    )
