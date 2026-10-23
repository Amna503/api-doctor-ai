from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from ..analysis.impact import map_impact
from ..analysis.loader import LoadedSpec
from ..models import Consumer, Finding, ImpactReport
from .base import BaseAgent


class ImpactMapperInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    consumers: list[Consumer] = Field(default_factory=list)
    finding_count: int = 0


@dataclass(frozen=True)
class ImpactMapperDependencies:
    old: LoadedSpec
    new: LoadedSpec
    findings: list[Finding]


@dataclass(frozen=True)
class ImpactMapperOutput:
    impact: ImpactReport
    affected_consumer_count: int
    unclaimed_endpoint_count: int


class ImpactMapper(BaseAgent):
    name = "Impact Mapper"
    responsibility = (
        "Map deterministic findings onto API operations and declared consumer-to-endpoint "
        "dependencies, then build the dependency graph. It does not infer undocumented consumers."
    )
    timeout_seconds = 5.0
    max_retries = 0

    def run(
        self, payload: ImpactMapperInput, deps: ImpactMapperDependencies
    ) -> ImpactMapperOutput:
        impact = map_impact(deps.old, deps.new, deps.findings, payload.consumers)
        return ImpactMapperOutput(
            impact=impact,
            affected_consumer_count=len(impact.consumers),
            unclaimed_endpoint_count=len(impact.unclaimed_endpoints),
        )
