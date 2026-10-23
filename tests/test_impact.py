from __future__ import annotations

import copy

from app.agents.contract_analyzer import ContractAnalyzer, ContractAnalyzerInput
from app.analysis.impact import map_impact
from app.models import Consumer


def test_declared_consumers_are_mapped_to_findings(sample_old, sample_new, sample_consumers):
    analysis = ContractAnalyzer().run(
        ContractAnalyzerInput(old_spec=sample_old, new_spec=sample_new)
    )
    impact = map_impact(
        analysis.old,
        analysis.new,
        analysis.findings,
        [Consumer(**item) for item in sample_consumers],
    )
    assert len(impact.consumers) == 3
    names = {item.name for item in impact.consumers}
    assert names == {"Mobile App (iOS)", "Partner Portal", "Billing Worker"}
    mobile = next(item for item in impact.consumers if item.name == "Mobile App (iOS)")
    assert mobile.severity == "critical"
    assert "GET /v1/payments" in mobile.affected_endpoints


def test_undeclared_endpoint_is_reported_as_unclaimed(sample_old, sample_new):
    analysis = ContractAnalyzer().run(
        ContractAnalyzerInput(old_spec=sample_old, new_spec=sample_new)
    )
    consumers = [Consumer(name="Only One Endpoint", endpoints=["GET /v1/customers/{customerId}"])]
    impact = map_impact(analysis.old, analysis.new, analysis.findings, consumers)
    assert "GET /v1/payments" in impact.unclaimed_endpoints
    assert "GET /v1/payments" not in impact.consumers[0].affected_endpoints


def test_graph_contains_consumer_and_endpoint_nodes(sample_old, sample_new, sample_consumers):
    analysis = ContractAnalyzer().run(
        ContractAnalyzerInput(old_spec=sample_old, new_spec=sample_new)
    )
    impact = map_impact(
        analysis.old,
        analysis.new,
        analysis.findings,
        [Consumer(**item) for item in sample_consumers],
    )
    kinds = {node.kind for node in impact.graph.nodes}
    assert kinds == {"consumer", "endpoint"}
    assert impact.graph.edges
    assert all(edge.source.startswith("consumer:") for edge in impact.graph.edges)
