from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from ..analysis.differ import count_endpoint_changes, diff_specs
from ..analysis.loader import LoadedSpec, load_spec
from ..models import Finding
from .base import BaseAgent


class ContractAnalyzerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    old_spec: dict
    new_spec: dict
    max_findings: int = Field(default=250, ge=1, le=500)


@dataclass(frozen=True)
class ContractAnalyzerOutput:
    old: LoadedSpec
    new: LoadedSpec
    findings: list[Finding]
    endpoints_added: int
    endpoints_removed: int
    operations_affected: int


class ContractAnalyzer(BaseAgent):
    name = "Contract Analyzer"
    responsibility = (
        "Validate both OpenAPI documents and identify contract changes with deterministic, "
        "evidence-backed rules. It never calls an AI model."
    )
    timeout_seconds = 5.0
    max_retries = 0

    def run(self, payload: ContractAnalyzerInput) -> ContractAnalyzerOutput:
        old = load_spec(payload.old_spec, "old specification")
        new = load_spec(payload.new_spec, "new specification")
        findings = diff_specs(old, new, max_findings=payload.max_findings)
        added, removed, affected = count_endpoint_changes(old, new, findings)
        return ContractAnalyzerOutput(
            old=old,
            new=new,
            findings=findings,
            endpoints_added=added,
            endpoints_removed=removed,
            operations_affected=affected,
        )
