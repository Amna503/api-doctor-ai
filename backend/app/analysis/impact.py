from __future__ import annotations

from collections import defaultdict

from ..models import (
    AffectedConsumer,
    AffectedEndpoint,
    Consumer,
    Finding,
    GraphEdge,
    GraphNode,
    ImpactGraph,
    ImpactReport,
    Severity,
)
from .differ import SEVERITY_ORDER
from .loader import LoadedSpec


def _max_severity(severities: list[str]) -> Severity:
    if not severities:
        return "info"
    return sorted(severities, key=lambda item: SEVERITY_ORDER.get(item, 9))[0]  # type: ignore[return-value]


def map_impact(
    old: LoadedSpec,
    new: LoadedSpec,
    findings: list[Finding],
    consumers: list[Consumer],
) -> ImpactReport:
    endpoint_findings: dict[tuple[str, str], list[Finding]] = defaultdict(list)
    for finding in findings:
        if finding.method and finding.path:
            endpoint_findings[(finding.method, finding.path)].append(finding)

    declared_by_endpoint: dict[tuple[str, str], list[str]] = defaultdict(list)
    for consumer in consumers:
        for endpoint in consumer.endpoints:
            method, path = endpoint.split(" ", 1)
            declared_by_endpoint[(method, path)].append(consumer.name)

    affected: list[AffectedEndpoint] = []
    for (method, path), items in sorted(
        endpoint_findings.items(), key=lambda item: (item[0][1], item[0][0])
    ):
        affected.append(
            AffectedEndpoint(
                method=method,
                path=path,
                severity=_max_severity([item.severity for item in items]),
                breaking=any(item.breaking for item in items),
                finding_ids=[item.id for item in items],
                consumers=sorted(set(declared_by_endpoint.get((method, path), []))),
                exists_in_new=f"{method} {path}" in new.operations,
            )
        )

    affected_by_consumer: dict[str, AffectedConsumer] = {}
    for consumer in consumers:
        endpoint_ids: list[str] = []
        finding_ids: list[str] = []
        severities: list[str] = []
        for endpoint in consumer.endpoints:
            method, path = endpoint.split(" ", 1)
            if (method, path) in endpoint_findings:
                endpoint_ids.append(f"{method} {path}")
                items = endpoint_findings[(method, path)]
                finding_ids.extend(item.id for item in items)
                severities.extend(item.severity for item in items)
        if endpoint_ids:
            affected_by_consumer[consumer.name] = AffectedConsumer(
                name=consumer.name,
                owner=consumer.owner,
                affected_endpoints=sorted(endpoint_ids),
                finding_ids=sorted(set(finding_ids)),
                severity=_max_severity(severities),
            )

    unclaimed = [
        f"{item.method} {item.path}"
        for item in affected
        if not item.consumers
    ]

    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    endpoint_node_ids: set[str] = set()
    for item in affected[:32]:
        node_id = f"endpoint:{item.method} {item.path}"
        endpoint_node_ids.add(f"{item.method} {item.path}")
        nodes.append(
            GraphNode(
                id=node_id,
                label=f"{item.method} {item.path}",
                kind="endpoint",
                group=item.severity if item.breaking else "stable",
                severity=item.severity,
                meta={
                    "method": item.method,
                    "path": item.path,
                    "breaking": item.breaking,
                    "exists_in_new": item.exists_in_new,
                    "finding_ids": item.finding_ids,
                    "consumers": item.consumers,
                },
            )
        )
    for consumer in consumers[:14]:
        node_id = f"consumer:{consumer.name}"
        nodes.append(
            GraphNode(
                id=node_id,
                label=consumer.name,
                kind="consumer",
                group="affected" if consumer.name in affected_by_consumer else "unaffected",
                meta={
                    "owner": consumer.owner,
                    "affected": consumer.name in affected_by_consumer,
                    "endpoints": consumer.endpoints,
                },
            )
        )
        for endpoint in consumer.endpoints:
            if endpoint in endpoint_node_ids:
                edges.append(
                    GraphEdge(
                        source=node_id,
                        target=f"endpoint:{endpoint}",
                        label="declares",
                    )
                )

    return ImpactReport(
        affected_endpoints=affected,
        consumers=sorted(
            affected_by_consumer.values(),
            key=lambda item: (SEVERITY_ORDER.get(item.severity, 9), item.name),
        ),
        unclaimed_endpoints=unclaimed,
        graph=ImpactGraph(nodes=nodes, edges=edges),
    )
