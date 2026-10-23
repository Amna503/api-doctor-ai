from __future__ import annotations

from typing import Any

from ..models import Consumer, Finding, MigrationPlan, MigrationStep


def _replacement_endpoint(method: str, path: str, endpoints: list[str]) -> str | None:
    path_parts = [part for part in path.split("/") if part]
    candidates: list[tuple[int, str]] = []
    for endpoint in endpoints:
        parts = endpoint.split(" ", 1)
        if len(parts) != 2 or parts[0] != method:
            continue
        candidate_parts = [part for part in parts[1].split("/") if part]
        suffix = 0
        for left, right in zip(reversed(path_parts), reversed(candidate_parts)):
            if left.lower() in {"v1", "v2", "v3", "v4", "api"}:
                break
            if left == right:
                suffix += 1
            else:
                break
        if suffix > 0:
            candidates.append((suffix, endpoint))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return candidates[0][1]


def _consumers_for(method: str, path: str, consumers: list[Consumer]) -> list[str]:
    target = f"{method} {path}"
    return sorted(
        consumer.name
        for consumer in consumers
        if target in consumer.endpoints
    )


def _code_before(method: str, path: str, params: dict[str, Any] | None = None) -> str:
    param_text = f", params={params!r}" if params else ""
    return f'# legacy consumer\nresponse = client.request("{method}", "{path}"{param_text})'


def _code_after(method: str, path: str, params: dict[str, Any] | None = None, note: str = "") -> str:
    param_text = f", params={params!r}" if params else ""
    prefix = f"# {note}\n" if note else ""
    return f'{prefix}response = client.request("{method}", "{path}"{param_text})'


def build_fallback_plan(
    findings: list[Finding],
    consumers: list[Consumer],
    new_endpoints: list[str],
    model: str,
    prompt_version: str,
    reason: str,
    generated_at: Any = None,
) -> MigrationPlan:
    breaking = [item for item in findings if item.breaking]
    steps: list[MigrationStep] = []
    used_ids: set[str] = set()

    removed = [item for item in breaking if item.kind == "endpoint_removed"]
    for finding in removed[:4]:
        replacement = _replacement_endpoint(finding.method or "GET", finding.path or "/", new_endpoints)
        affected = _consumers_for(finding.method or "", finding.path or "", consumers)
        ids = [finding.id]
        title = f"Bridge {finding.method} {finding.path}"
        if replacement:
            new_method, new_path = replacement.split(" ", 1)
            detail = (
                f"The route is removed in the new contract. Keep a deprecated alias for "
                f"{finding.method} {finding.path} during the migration window, then move callers to "
                f"{replacement}."
            )
            if affected:
                detail += f" Declared consumers to coordinate: {', '.join(affected)}."
            step = MigrationStep(
                id=f"MIG-{len(steps) + 1:02d}",
                title=title,
                detail=detail,
                finding_ids=ids,
                confidence=0.72,
                code_before=_code_before(finding.method or "GET", finding.path or "/"),
                code_after=_code_after(new_method, new_path, note="replacement endpoint"),
                notes="Deterministic fallback guidance; no model was called for this step.",
            )
        else:
            detail = (
                f"{finding.method} {finding.path} has no obvious versioned replacement in the new document. "
                "Do not remove it until the API owner confirms a replacement or an explicit deprecation window."
            )
            if affected:
                detail += f" Affected consumers: {', '.join(affected)}."
            step = MigrationStep(
                id=f"MIG-{len(steps) + 1:02d}",
                title=title,
                detail=detail,
                finding_ids=ids,
                confidence=0.6,
                code_before=_code_before(finding.method or "GET", finding.path or "/"),
                code_after="# No documented replacement. Open a migration ticket with the API owner.",
                notes="No safe replacement could be inferred deterministically.",
            )
        steps.append(step)
        used_ids.update(ids)

    required = [
        item
        for item in breaking
        if item.kind
        in {
            "parameter_added_required",
            "parameter_required_changed",
            "request_body_required_added",
            "request_body_required_changed",
            "request_property_added_required",
            "request_property_required_added",
        }
    ]
    for finding in required[:3]:
        if finding.id in used_ids:
            continue
        affected = _consumers_for(finding.method or "", finding.path or "", consumers)
        detail = (
            f"{finding.title}. Update the request to include the new required input, or ask the provider "
            "to make it optional during the migration window."
        )
        if affected:
            detail += f" Declared consumers: {', '.join(affected)}."
        steps.append(
            MigrationStep(
                id=f"MIG-{len(steps) + 1:02d}",
                title=f"Update request for {finding.location}",
                detail=detail,
                finding_ids=[finding.id],
                confidence=0.68,
                code_before=f"# old request\n# {finding.location}",
                code_after=(
                    f"# new request: include {finding.parameter or 'the new required field'} "
                    "with a valid default or configured value"
                ),
                notes="Deterministic fallback guidance; confirm validation rules with the API owner.",
            )
        )
        used_ids.add(finding.id)

    type_and_field = [
        item
        for item in breaking
        if item.kind
        in {
            "request_type_changed",
            "response_type_changed",
            "request_property_removed",
            "response_property_removed",
            "request_property_type_changed",
            "response_property_type_changed",
            "request_enum_narrowed",
            "response_enum_narrowed",
        }
        and item.id not in used_ids
    ]
    for finding in type_and_field[:3]:
        detail = (
            f"{finding.title}. Introduce a mapping layer or tolerant parser on consumers before the provider "
            "removes the old shape. Publish both shapes through a versioned response or deprecation window."
        )
        steps.append(
            MigrationStep(
                id=f"MIG-{len(steps) + 1:02d}",
                title=f"Add compatibility mapping for {finding.location}",
                detail=detail,
                finding_ids=[finding.id],
                confidence=0.64,
                code_before=f"# parse old shape at {finding.location}",
                code_after=(
                    f"# parse new shape, normalize missing/renamed fields, and keep a feature flag "
                    f"for {finding.location}"
                ),
                notes="Field/type changes require a deliberate mapping decision; not auto-patched.",
            )
        )
        used_ids.add(finding.id)

    security = [item for item in breaking if item.kind.startswith("security") or item.kind == "servers_changed"]
    for finding in security[:2]:
        if finding.id in used_ids:
            continue
        steps.append(
            MigrationStep(
                id=f"MIG-{len(steps) + 1:02d}",
                title=f"Coordinate infrastructure change: {finding.title}",
                detail=(
                    f"{finding.detail} Roll out credentials and base URL changes with both old and new "
                    "configurations accepted until traffic drains from the old path."
                ),
                finding_ids=[finding.id],
                confidence=0.7,
                code_before="# old auth/base URL",
                code_after="# new auth/base URL behind a config flag; monitor 401/404 rates",
            )
        )
        used_ids.add(finding.id)

    remaining = [item for item in breaking if item.id not in used_ids]
    if remaining:
        steps.append(
            MigrationStep(
                id=f"MIG-{len(steps) + 1:02d}",
                title=f"Review {len(remaining)} additional breaking finding(s)",
                detail=(
                    "These findings were not grouped into an automated step: "
                    + "; ".join(f"{item.id} {item.title}" for item in remaining[:8])
                    + ". Assign each to its owning contract or consumer team."
                ),
                finding_ids=[item.id for item in remaining[:12]],
                confidence=0.5,
                notes="Insufficient deterministic signal for a safe automated recommendation.",
            )
        )
        used_ids.update(item.id for item in remaining[:12])

    if not steps:
        steps.append(
            MigrationStep(
                id="MIG-01",
                title="No breaking changes detected",
                detail=(
                    "The deterministic diff found no breaking changes. Keep the generated contract tests "
                    "in CI to catch regressions."
                ),
                finding_ids=[],
                confidence=0.95,
            )
        )

    summary = (
        f"Deterministic analysis found {len(breaking)} breaking change(s) across "
        f"{len({(item.method, item.path) for item in breaking if item.path})} affected endpoint(s). "
        f"Declared consumers: {len(consumers)}. "
        f"Gemma guidance is unavailable ({reason}); this plan is rule-based and does not claim fixes were applied."
    )
    strategy = (
        "1) Keep legacy routes/fields reachable through a compatibility window. "
        "2) Migrate consumers in severity order (critical endpoints first). "
        "3) Add the new required inputs and update parsers behind feature flags. "
        "4) Run the generated contract checks before and after rollout. "
        "5) Remove compatibility shims only after declared consumers confirm migration."
    )
    return MigrationPlan(
        source="fallback",
        model=model,
        prompt_version=prompt_version,
        summary=summary,
        strategy=strategy,
        steps=steps[:10],
        warnings=[
            "Fallback mode: no AI model output is presented as model analysis.",
            "Deterministic findings are authoritative; suggestions still need owner review.",
        ],
        generated_at=generated_at,
    )
