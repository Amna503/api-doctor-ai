from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Severity = Literal["critical", "high", "medium", "low", "info"]
TraceStatus = Literal["success", "fallback", "error", "skipped"]
TestStatus = Literal["passed", "failed", "skipped"]
RiskLevel = Literal["critical", "high", "medium", "low", "clean"]
SourceKind = Literal["deterministic", "gemma", "fallback", "sandbox"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Consumer(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    owner: str | None = Field(default=None, max_length=120)
    endpoints: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("endpoints")
    @classmethod
    def validate_endpoints(cls, value: list[str]) -> list[str]:
        for item in value:
            parts = item.strip().split(" ", 1)
            if len(parts) != 2 or parts[0].upper() not in {
                "GET",
                "POST",
                "PUT",
                "PATCH",
                "DELETE",
                "HEAD",
                "OPTIONS",
                "TRACE",
            }:
                raise ValueError(
                    f"Consumer endpoint '{item}' must use 'METHOD /path' format"
                )
            if not parts[1].startswith("/"):
                raise ValueError(f"Consumer endpoint '{item}' must start with /")
        return [
            f"{item.split(' ', 1)[0].upper()} {item.split(' ', 1)[1].strip()}"
            for item in value
        ]


class AnalyzeRequest(StrictModel):
    old_spec: dict[str, Any]
    new_spec: dict[str, Any]
    consumers: list[Consumer] = Field(default_factory=list, max_length=50)
    consumer_source: str | None = Field(default=None, max_length=200)


class VerifyRequest(AnalyzeRequest):
    apply_compatibility_patch: bool = False


class Finding(StrictModel):
    id: str
    rule: str
    kind: str
    severity: Severity
    breaking: bool
    title: str
    detail: str
    method: str | None = None
    path: str | None = None
    location: str
    evidence: str
    old_value: Any = None
    new_value: Any = None
    confidence: float = Field(default=1.0, ge=0, le=1)
    source: SourceKind = "deterministic"
    suggestion: str | None = None
    schema_pointer: str | None = None
    parameter: str | None = None
    old_fragment: Any = None
    new_fragment: Any = None


class SpecMeta(StrictModel):
    title: str
    version: str
    openapi: str
    endpoint_count: int
    operations: list[str]
    servers: list[str] = Field(default_factory=list)


class Summary(StrictModel):
    analysis_id: str
    breaking_changes: int
    non_breaking_changes: int
    total_changes: int
    by_severity: dict[str, int]
    endpoints_added: int
    endpoints_removed: int
    operations_affected: int
    old_endpoint_count: int
    new_endpoint_count: int


class AffectedEndpoint(StrictModel):
    method: str
    path: str
    severity: Severity
    breaking: bool
    finding_ids: list[str]
    consumers: list[str]
    exists_in_new: bool


class AffectedConsumer(StrictModel):
    name: str
    owner: str | None = None
    affected_endpoints: list[str]
    finding_ids: list[str]
    severity: Severity


class GraphNode(StrictModel):
    id: str
    label: str
    kind: Literal["consumer", "endpoint"]
    group: str
    severity: Severity | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(StrictModel):
    source: str
    target: str
    label: str | None = None


class ImpactGraph(StrictModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class ImpactReport(StrictModel):
    affected_endpoints: list[AffectedEndpoint]
    consumers: list[AffectedConsumer]
    unclaimed_endpoints: list[str]
    graph: ImpactGraph


class MigrationStep(StrictModel):
    id: str
    title: str
    detail: str
    finding_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.8, ge=0, le=1)
    code_before: str | None = None
    code_after: str | None = None
    notes: str | None = None


class MigrationPlan(StrictModel):
    source: Literal["gemma", "fallback"]
    model: str
    prompt_version: str
    summary: str
    strategy: str
    steps: list[MigrationStep]
    warnings: list[str] = Field(default_factory=list)
    generated_at: datetime | None = None


class GeneratedTest(StrictModel):
    id: str
    name: str
    description: str
    type: Literal["endpoint_available", "legacy_request", "response_contract"]
    method: str
    path: str
    finding_ids: list[str]
    check: dict[str, Any]
    expected: str
    code: str


class GeneratedTests(StrictModel):
    source: Literal["deterministic"] = "deterministic"
    sandbox: str = "structured-json-checks/v1"
    note: str
    tests: list[GeneratedTest]


class ExecutionTrace(StrictModel):
    agent: str
    action: str
    status: TraceStatus
    started_at: datetime
    duration_ms: int
    attempt: int = 1
    provider: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    detail: str | None = None
    error: str | None = None
    evidence_count: int | None = None


class RiskAssessment(StrictModel):
    score: int = Field(ge=0, le=100)
    level: RiskLevel
    verified: bool
    status: Literal["unresolved_risks", "verified_compatible", "not_executed"]
    unresolved_findings: int
    resolved_findings: int
    summary: str
    unresolved: list[str]
    evidence_coverage: float = Field(ge=0, le=1)


class CompatibilityPatch(StrictModel):
    applied: bool
    description: str
    changes: list[str]
    remaining_unpatchable: list[str] = Field(default_factory=list)
    residual_breaking_changes: int = 0
    residual_findings: list[str] = Field(default_factory=list)


class AnalysisResult(StrictModel):
    analysis_id: str
    generated_at: datetime
    old_spec: SpecMeta
    new_spec: SpecMeta
    summary: Summary
    findings: list[Finding]
    impact: ImpactReport
    migration: MigrationPlan
    tests: GeneratedTests
    risk: RiskAssessment
    traces: list[ExecutionTrace]
    deterministic_engine: str = "api-doctor-diff/v1"
    disclaimer: str


class TestResult(StrictModel):
    test_id: str
    name: str
    type: str
    method: str
    path: str
    finding_ids: list[str]
    status: TestStatus
    expected: str
    actual: str
    evidence: list[str]
    duration_ms: int


class VerificationResult(StrictModel):
    analysis_id: str
    run_id: str
    executed_at: datetime
    duration_ms: int
    sandbox: str
    sandbox_notes: str
    total: int
    passed: int
    failed: int
    skipped: int
    results: list[TestResult]
    risk: RiskAssessment
    compatibility_patch: CompatibilityPatch | None = None
    traces: list[ExecutionTrace]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str
    environment: str
    model_provider: str
    model: str
    model_configured: bool
    model_fallback: str
    deterministic_engine: str
    timestamp: datetime
    uptime_seconds: int
