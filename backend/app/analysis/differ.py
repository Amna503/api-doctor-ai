from __future__ import annotations

import copy
import json
from typing import Any

from ..models import Finding
from .loader import LoadedSpec, OperationView, compact_json, schema_types

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
SEVERITY_WEIGHT = {"critical": 30, "high": 18, "medium": 8, "low": 3, "info": 0}


def escape_pointer(token: Any) -> str:
    return str(token).replace("~", "~0").replace("/", "~1")


def _raw_param_pointer(
    spec: dict[str, Any], path: str, method: str, name: str, location: str
) -> str | None:
    path_item = (spec.get("paths") or {}).get(path)
    if not isinstance(path_item, dict):
        return None
    op = path_item.get(method.lower())
    groups = (("op", op.get("parameters") if isinstance(op, dict) else None, f"/paths/{escape_pointer(path)}/{method.lower()}/parameters"),
              ("path", path_item.get("parameters"), f"/paths/{escape_pointer(path)}/parameters"))
    for _label, params, base in groups:
        if not isinstance(params, list):
            continue
        for index, param in enumerate(params):
            if not isinstance(param, dict) or "$ref" in param:
                continue
            if param.get("name") == name and param.get("in") == location:
                return f"{base}/{index}"
    return None


def _operation_pointer(path: str, method: str) -> str:
    return f"/paths/{escape_pointer(path)}/{method.lower()}"


def _schema_pointer_for_request(spec: dict[str, Any], op: OperationView) -> str | None:
    path_item = (spec.get("paths") or {}).get(op.path)
    if not isinstance(path_item, dict):
        return None
    raw_op = path_item.get(op.method.lower())
    if not isinstance(raw_op, dict):
        return None
    content = ((raw_op.get("requestBody") or {}).get("content") or {})
    if not isinstance(content, dict) or not content:
        return None
    media = "application/json" if "application/json" in content else next(iter(content))
    return f"{_operation_pointer(op.path, op.method)}/requestBody/content/{escape_pointer(media)}/schema"


def _schema_pointer_for_response(
    spec: dict[str, Any], op: OperationView, code: str
) -> str | None:
    path_item = (spec.get("paths") or {}).get(op.path)
    if not isinstance(path_item, dict):
        return None
    raw_op = path_item.get(op.method.lower())
    if not isinstance(raw_op, dict):
        return None
    response = ((raw_op.get("responses") or {}).get(code) or {})
    if not isinstance(response, dict) or "$ref" in response:
        return None
    content = response.get("content") or {}
    if not isinstance(content, dict) or not content:
        return None
    media = "application/json" if "application/json" in content else next(iter(content))
    return (
        f"{_operation_pointer(op.path, op.method)}/responses/{escape_pointer(code)}"
        f"/content/{escape_pointer(media)}/schema"
    )


class DiffCollector:
    def __init__(self, cap: int = 250) -> None:
        self._items: list[Finding] = []
        self.cap = cap

    def emit(
        self,
        *,
        rule: str,
        kind: str,
        severity: str,
        breaking: bool,
        title: str,
        detail: str,
        location: str,
        evidence: str,
        method: str | None = None,
        path: str | None = None,
        old_value: Any = None,
        new_value: Any = None,
        suggestion: str | None = None,
        schema_pointer: str | None = None,
        parameter: str | None = None,
        old_fragment: Any = None,
        new_fragment: Any = None,
        confidence: float = 1.0,
    ) -> None:
        if len(self._items) >= self.cap:
            return
        self._items.append(
            Finding(
                id="PENDING",
                rule=rule,
                kind=kind,
                severity=severity,  # type: ignore[arg-type]
                breaking=breaking,
                title=title,
                detail=detail,
                method=method,
                path=path,
                location=location,
                evidence=evidence,
                old_value=old_value,
                new_value=new_value,
                confidence=confidence,
                source="deterministic",
                suggestion=suggestion,
                schema_pointer=schema_pointer,
                parameter=parameter,
                old_fragment=old_fragment,
                new_fragment=new_fragment,
            )
        )

    def finalize(self) -> list[Finding]:
        ordered = sorted(
            self._items,
            key=lambda f: (
                SEVERITY_ORDER[f.severity],
                f.path or "",
                f.method or "",
                f.location,
            ),
        )
        out: list[Finding] = []
        for index, finding in enumerate(ordered, start=1):
            out.append(finding.model_copy(update={"id": f"CHG-{index:03d}"}))
        return out


def _type_change_is_compatible(old_types: list[str], new_types: list[str]) -> bool:
    old_set = set(old_types)
    new_set = set(new_types)
    if not old_set or not new_set:
        return True
    if "null" in old_set and "null" not in new_set:
        return False
    old_non_null = old_set - {"null"}
    new_non_null = new_set - {"null"}
    if old_non_null == new_non_null:
        return True
    if old_non_null <= new_non_null:
        return True
    if old_non_null == {"integer"} and new_non_null == {"number"}:
        return True
    return False


def _compare_schema(
    collector: DiffCollector,
    old_schema: dict[str, Any] | None,
    new_schema: dict[str, Any] | None,
    *,
    context: str,
    method: str,
    path: str,
    location: str,
    pointer: str | None,
    seen: set[tuple[int, int]] | None = None,
) -> None:
    if old_schema is None and new_schema is None:
        return
    seen = seen or set()
    pair = (id(old_schema), id(new_schema))
    if pair in seen:
        return
    seen.add(pair)
    prefix = "request" if context == "request" else "response"
    schema_word = "request body" if context == "request" else "response body"

    if old_schema is None:
        if context == "request":
            collector.emit(
                rule="request.body.schema_added",
                kind="request_body_added",
                severity="high",
                breaking=True,
                title="Request body schema added",
                detail=f"A schema was added to the {schema_word} at {location}; legacy clients may not send a body.",
                location=location,
                evidence=compact_json(new_schema),
                method=method,
                path=path,
                new_value=new_schema,
                suggestion="Document the new body and roll it out only with a tolerant fallback.",
                schema_pointer=pointer,
            )
        return
    if new_schema is None:
        if context == "response":
            collector.emit(
                rule="response.body.schema_removed",
                kind="response_body_removed",
                severity="high",
                breaking=True,
                title="Response body schema removed",
                detail=f"The {schema_word} at {location} no longer declares a schema, so typed consumers may break.",
                location=location,
                evidence=compact_json(old_schema),
                method=method,
                path=path,
                old_value=old_schema,
                suggestion="Keep the response schema or version the operation.",
                schema_pointer=pointer,
                old_fragment=old_schema,
            )
        return

    old_types = schema_types(old_schema)
    new_types = schema_types(new_schema)
    if not _type_change_is_compatible(old_types, new_types):
        severity = "high" if context == "request" or old_types != new_types else "medium"
        collector.emit(
            rule=f"{prefix}.type_changed",
            kind=f"{prefix}_type_changed",
            severity=severity,
            breaking=True,
            title=f"{'Request' if context == 'request' else 'Response'} type changed",
            detail=f"{location} changed type from {', '.join(old_types) or 'unspecified'} to {', '.join(new_types) or 'unspecified'}.",
            location=location,
            evidence=f"old={compact_json(old_schema)} new={compact_json(new_schema)}",
            method=method,
            path=path,
            old_value=old_schema,
            new_value=new_schema,
            suggestion="Keep the old type/field for at least one deprecation window or publish a versioned endpoint.",
            schema_pointer=pointer,
            old_fragment=old_schema,
            new_fragment=new_schema,
        )
        return

    if "null" in old_types and "null" not in new_types:
        collector.emit(
            rule=f"{prefix}.nullable_removed",
            kind=f"{prefix}_nullable_removed",
            severity="medium",
            breaking=True,
            title="Nullable constraint removed",
            detail=f"{location} no longer accepts null values.",
            location=location,
            evidence=f"old types={old_types} new types={new_types}",
            method=method,
            path=path,
            old_value=old_schema,
            new_value=new_schema,
            suggestion="Continue accepting null during the deprecation window.",
            schema_pointer=pointer,
            old_fragment=old_schema,
        )

    old_enum = old_schema.get("enum") if isinstance(old_schema.get("enum"), list) else None
    new_enum = new_schema.get("enum") if isinstance(new_schema.get("enum"), list) else None
    if old_enum is not None and new_enum is not None:
        removed = [value for value in old_enum if value not in new_enum]
        if removed:
            collector.emit(
                rule=f"{prefix}.enum_narrowed",
                kind=f"{prefix}_enum_narrowed",
                severity="medium",
                breaking=True,
                title="Enum values removed",
                detail=f"{location} no longer accepts {removed}.",
                location=location,
                evidence=f"removed={compact_json(removed)} old={compact_json(old_enum)} new={compact_json(new_enum)}",
                method=method,
                path=path,
                old_value=old_enum,
                new_value=new_enum,
                suggestion="Accept the removed values with a deprecation warning before removing them.",
                schema_pointer=pointer,
                old_fragment=old_schema,
            )
    elif old_enum is None and new_enum is not None:
        collector.emit(
            rule=f"{prefix}.enum_added",
            kind=f"{prefix}_enum_added",
            severity="info",
            breaking=False,
            title="Enum constraint added",
            detail=f"{location} now declares a fixed enum. Verify legacy values are all included.",
            location=location,
            evidence=compact_json(new_enum),
            method=method,
            path=path,
            new_value=new_enum,
            confidence=0.8,
        )
    elif old_enum is not None and new_enum is None:
        collector.emit(
            rule=f"{prefix}.enum_relaxed",
            kind=f"{prefix}_enum_relaxed",
            severity="info",
            breaking=False,
            title="Enum constraint relaxed",
            detail=f"{location} no longer restricts values to a fixed enum.",
            location=location,
            evidence=f"old={compact_json(old_enum)}",
            method=method,
            path=path,
            old_value=old_enum,
        )

    old_format = old_schema.get("format")
    new_format = new_schema.get("format")
    if old_format and new_format and old_format != new_format:
        collector.emit(
            rule=f"{prefix}.format_changed",
            kind=f"{prefix}_format_changed",
            severity="medium" if context == "request" else "low",
            breaking=context == "request",
            title="Schema format changed",
            detail=f"{location} format changed from {old_format} to {new_format}.",
            location=location,
            evidence=f"old={old_format} new={new_format}",
            method=method,
            path=path,
            old_value=old_format,
            new_value=new_format,
            suggestion="Confirm serializers/parsers on consumers support the new format.",
            schema_pointer=pointer,
        )

    old_types_non_null = [t for t in old_types if t != "null"]
    new_types_non_null = [t for t in new_types if t != "null"]
    if "object" in old_types_non_null and "object" in new_types_non_null:
        old_props = old_schema.get("properties") if isinstance(old_schema.get("properties"), dict) else {}
        new_props = new_schema.get("properties") if isinstance(new_schema.get("properties"), dict) else {}
        old_required = set(old_schema.get("required") or [])
        new_required = set(new_schema.get("required") or [])
        props_pointer = f"{pointer}/properties" if pointer else None
        for name in sorted(set(old_props) - set(new_props)):
            collector.emit(
                rule=f"{prefix}.property_removed",
                kind=f"{prefix}_property_removed",
                severity="high",
                breaking=True,
                title=f"{'Request' if context == 'request' else 'Response'} property removed: {name}",
                detail=f"Property '{name}' was removed from {location}.",
                location=f"{location}.{name}",
                evidence=f"removed schema={compact_json(old_props[name])}",
                method=method,
                path=path,
                old_value=old_props[name],
                new_value=None,
                suggestion=f"Restore '{name}' (deprecated) or migrate all consumers before removal.",
                schema_pointer=props_pointer,
                parameter=name,
                old_fragment=old_props[name],
            )
        for name in sorted(set(new_props) - set(old_props)):
            is_required = name in new_required
            if is_required:
                collector.emit(
                    rule=f"{prefix}.property_required_added",
                    kind=f"{prefix}_property_added_required",
                    severity="high",
                    breaking=True,
                    title=f"New required {'request' if context == 'request' else 'response'} property: {name}",
                    detail=f"'{name}' is new and required in {location}.",
                    location=f"{location}.{name}",
                    evidence=f"required={compact_json(new_required)} schema={compact_json(new_props[name])}",
                    method=method,
                    path=path,
                    new_value=new_props[name],
                    suggestion=f"Make '{name}' optional or add a compatibility default before requiring it.",
                    schema_pointer=props_pointer,
                    parameter=name,
                    new_fragment=new_props[name],
                )
            else:
                collector.emit(
                    rule=f"{prefix}.property_added",
                    kind=f"{prefix}_property_added",
                    severity="info",
                    breaking=False,
                    title=f"Optional {'request' if context == 'request' else 'response'} property added: {name}",
                    detail=f"An optional property was added to {location}.",
                    location=f"{location}.{name}",
                    evidence=compact_json(new_props[name]),
                    method=method,
                    path=path,
                    new_value=new_props[name],
                )
        for name in sorted(set(old_props) & set(new_props)):
            if name not in new_required and name in old_required:
                collector.emit(
                    rule=f"{prefix}.required_relaxed",
                    kind=f"{prefix}_required_relaxed",
                    severity="info",
                    breaking=False,
                    title=f"Required constraint relaxed: {name}",
                    detail=f"'{name}' is no longer required in {location}.",
                    location=f"{location}.{name}",
                    evidence=f"old required=true new required=false",
                    method=method,
                    path=path,
                    old_value=True,
                    new_value=False,
                )
            if name in new_required and name not in old_required:
                collector.emit(
                    rule=f"{prefix}.property_required_changed",
                    kind=f"{prefix}_property_required_added",
                    severity="high" if context == "request" else "medium",
                    breaking=True,
                    title=f"Property became required: {name}",
                    detail=f"'{name}' is now required in {location}, which can break legacy payloads.",
                    location=f"{location}.{name}",
                    evidence=f"new required={compact_json(sorted(new_required))}",
                    method=method,
                    path=path,
                    old_value=False,
                    new_value=True,
                    suggestion=f"Keep '{name}' optional for the deprecation window.",
                    schema_pointer=props_pointer,
                    parameter=name,
                )
            _compare_schema(
                collector,
                old_props[name],
                new_props[name],
                context=context,
                method=method,
                path=path,
                location=f"{location}.{name}",
                pointer=f"{props_pointer}/{escape_pointer(name)}" if props_pointer else None,
                seen=seen,
            )
        old_additional = old_schema.get("additionalProperties", True)
        new_additional = new_schema.get("additionalProperties", True)
        if old_additional is not False and new_additional is False:
            collector.emit(
                rule=f"{prefix}.additional_properties_disallowed",
                kind=f"{prefix}_additional_properties_disallowed",
                severity="medium",
                breaking=True,
                title="Additional properties disallowed",
                detail=f"{location} no longer allows undeclared properties.",
                location=location,
                evidence="additionalProperties changed to false",
                method=method,
                path=path,
                old_value=old_additional,
                new_value=False,
                suggestion="Continue accepting unknown properties or announce strict validation.",
                schema_pointer=pointer,
                old_fragment=old_schema,
            )
    elif "array" in old_types_non_null and "array" in new_types_non_null:
        _compare_schema(
            collector,
            old_schema.get("items") if isinstance(old_schema.get("items"), dict) else None,
            new_schema.get("items") if isinstance(new_schema.get("items"), dict) else None,
            context=context,
            method=method,
            path=path,
            location=f"{location}[]",
            pointer=f"{pointer}/items" if pointer else None,
            seen=seen,
        )


def _compare_security(
    collector: DiffCollector, old: OperationView, new: OperationView
) -> None:
    old_canonical = json.dumps(old.security, sort_keys=True)
    new_canonical = json.dumps(new.security, sort_keys=True)
    if old_canonical == new_canonical:
        return
    collector.emit(
        rule="security.requirements_changed",
        kind="security_changed",
        severity="high",
        breaking=True,
        title="Authentication requirements changed",
        detail=f"Security requirements changed for {old.key}.",
        location=f"{old.method} {old.path} security",
        evidence=f"old={old_canonical} new={new_canonical}",
        method=old.method,
        path=old.path,
        old_value=old.security,
        new_value=new.security,
        suggestion="Support both auth schemes during migration and communicate token changes.",
    )


def _compare_parameters(
    collector: DiffCollector, old: LoadedSpec, new: LoadedSpec, old_op: OperationView, new_op: OperationView
) -> None:
    old_keys = set(old_op.parameters)
    new_keys = set(new_op.parameters)
    for key in sorted(old_keys - new_keys, key=lambda item: (item[1], item[0])):
        name, where = key
        collector.emit(
            rule="parameter.removed",
            kind="parameter_removed",
            severity="high",
            breaking=True,
            title=f"{'Query' if where == 'query' else where.title()} parameter removed: {name}",
            detail=f"Parameter '{name}' (in {where}) was removed from {old_op.key}.",
            location=f"{old_op.method} {old_op.path} parameter {where}.{name}",
            evidence=compact_json(old_op.parameters[key]),
            method=old_op.method,
            path=old_op.path,
            old_value=old_op.parameters[key],
            new_value=None,
            suggestion=f"Continue accepting '{name}' as deprecated, or coordinate removal with consumers.",
            parameter=name,
            old_fragment=old_op.parameters[key],
        )
    for key in sorted(new_keys - old_keys, key=lambda item: (item[1], item[0])):
        name, where = key
        param = new_op.parameters[key]
        required = bool(param.get("required", False)) or where == "path"
        pointer = _raw_param_pointer(new.raw, new_op.path, new_op.method, name, where)
        if required:
            collector.emit(
                rule="parameter.required_added",
                kind="parameter_added_required",
                severity="high",
                breaking=True,
                title=f"New required parameter: {name}",
                detail=f"Parameter '{name}' (in {where}) is new and required on {new_op.key}.",
                location=f"{new_op.method} {new_op.path} parameter {where}.{name}",
                evidence=compact_json(param),
                method=new_op.method,
                path=new_op.path,
                new_value=param,
                suggestion=f"Make '{name}' optional or provide a default until consumers are updated.",
                schema_pointer=pointer,
                parameter=name,
                new_fragment=param,
            )
        else:
            collector.emit(
                rule="parameter.optional_added",
                kind="parameter_added_optional",
                severity="info",
                breaking=False,
                title=f"Optional parameter added: {name}",
                detail=f"Optional parameter '{name}' was added to {new_op.key}.",
                location=f"{new_op.method} {new_op.path} parameter {where}.{name}",
                evidence=compact_json(param),
                method=new_op.method,
                path=new_op.path,
                new_value=param,
            )
    for key in sorted(old_keys & new_keys):
        name, where = key
        old_param = old_op.parameters[key]
        new_param = new_op.parameters[key]
        pointer = _raw_param_pointer(new.raw, new_op.path, new_op.method, name, where)
        was_required = bool(old_param.get("required", False)) or where == "path"
        is_required = bool(new_param.get("required", False)) or where == "path"
        if is_required and not was_required:
            collector.emit(
                rule="parameter.required_changed",
                kind="parameter_required_changed",
                severity="high",
                breaking=True,
                title=f"Parameter became required: {name}",
                detail=f"Parameter '{name}' is now required on {new_op.key}.",
                location=f"{new_op.method} {new_op.path} parameter {where}.{name}",
                evidence=f"old required=false new required=true",
                method=new_op.method,
                path=new_op.path,
                old_value=False,
                new_value=True,
                suggestion=f"Keep '{name}' optional during migration.",
                schema_pointer=pointer,
                parameter=name,
            )
        elif was_required and not is_required:
            collector.emit(
                rule="parameter.required_relaxed",
                kind="parameter_required_relaxed",
                severity="info",
                breaking=False,
                title=f"Parameter became optional: {name}",
                detail=f"Parameter '{name}' is no longer required on {new_op.key}.",
                location=f"{new_op.method} {new_op.path} parameter {where}.{name}",
                evidence="old required=true new required=false",
                method=new_op.method,
                path=new_op.path,
                old_value=True,
                new_value=False,
            )
        old_schema = old_param.get("schema") if isinstance(old_param.get("schema"), dict) else {}
        new_schema = new_param.get("schema") if isinstance(new_param.get("schema"), dict) else {}
        _compare_schema(
            collector,
            old_schema,
            new_schema,
            context="request",
            method=new_op.method,
            path=new_op.path,
            location=f"{new_op.method} {new_op.path} parameter {where}.{name}",
            pointer=f"{pointer}/schema" if pointer else None,
        )


def _compare_operations(
    collector: DiffCollector, old: LoadedSpec, new: LoadedSpec
) -> None:
    for path in sorted(set(old.raw.get("paths", {})) | set(new.raw.get("paths", {}))):
        old_methods = old.path_item_methods.get(path, set())
        new_methods = new.path_item_methods.get(path, set())
        if path in new.path_item_methods and path not in old.path_item_methods:
            for method in sorted(new_methods):
                collector.emit(
                    rule="endpoint.added",
                    kind="endpoint_added",
                    severity="info",
                    breaking=False,
                    title=f"Endpoint added: {method} {path}",
                    detail=f"A new operation {method} {path} was added.",
                    location=f"{method} {path}",
                    evidence="new operation",
                    method=method,
                    path=path,
                    new_value={"method": method, "path": path},
                )
            continue
        for method in sorted(old_methods - new_methods):
            old_op = old.operations[f"{method} {path}"]
            collector.emit(
                rule="endpoint.removed",
                kind="endpoint_removed",
                severity="critical",
                breaking=True,
                title=f"Endpoint removed: {method} {path}",
                detail=f"{method} {path} no longer exists. Any consumer calling it receives 404/405.",
                location=f"{method} {path}",
                evidence=compact_json({"operationId": old_op.operation.get("operationId"), "summary": old_op.operation.get("summary")}),
                method=method,
                path=path,
                old_value={"method": method, "path": path},
                new_value=None,
                suggestion="Restore the route as a deprecated alias that forwards to the replacement endpoint.",
                schema_pointer=f"/paths/{escape_pointer(path)}/{method.lower()}",
                old_fragment=old_op.operation,
            )
        for method in sorted(new_methods - old_methods):
            collector.emit(
                rule="endpoint.added",
                kind="endpoint_added",
                severity="info",
                breaking=False,
                title=f"Endpoint added: {method} {path}",
                detail=f"A new operation {method} {path} was added.",
                location=f"{method} {path}",
                evidence="new operation",
                method=method,
                path=path,
                new_value={"method": method, "path": path},
            )
        for method in sorted(old_methods & new_methods):
            old_op = old.operations[f"{method} {path}"]
            new_op = new.operations[f"{method} {path}"]
            location_base = f"{method} {path}"
            if new_op.deprecated and not old_op.deprecated:
                collector.emit(
                    rule="operation.deprecated",
                    kind="operation_deprecated",
                    severity="low",
                    breaking=False,
                    title=f"Operation deprecated: {method} {path}",
                    detail="The operation is newly marked deprecated.",
                    location=location_base,
                    evidence="deprecated: true",
                    method=method,
                    path=path,
                    new_value=True,
                    suggestion="Plan the consumer migration before the eventual removal.",
                )
            _compare_parameters(collector, old, new, old_op, new_op)
            old_media = old_op.request_media_type
            new_media = new_op.request_media_type
            if old_op.request_schema is None and new_op.request_schema is not None:
                if new_op.request_required:
                    collector.emit(
                        rule="request.body.required_added",
                        kind="request_body_required_added",
                        severity="high",
                        breaking=True,
                        title="Required request body introduced",
                        detail=f"{method} {path} now requires a request body.",
                        location=f"{location_base} requestBody",
                        evidence=compact_json(new_op.request_schema),
                        method=method,
                        path=path,
                        new_value=new_op.request_schema,
                        suggestion="Accept requests without a body during the migration window.",
                        schema_pointer=f"{_operation_pointer(path, method)}/requestBody",
                    )
                else:
                    collector.emit(
                        rule="request.body.optional_added",
                        kind="request_body_added",
                        severity="low",
                        breaking=False,
                        title="Optional request body introduced",
                        detail=f"{method} {path} now documents an optional request body.",
                        location=f"{location_base} requestBody",
                        evidence=compact_json(new_op.request_schema),
                        method=method,
                        path=path,
                        new_value=new_op.request_schema,
                    )
            elif old_op.request_schema is not None and new_op.request_schema is None:
                collector.emit(
                    rule="request.body.removed",
                    kind="request_body_removed",
                    severity="medium",
                    breaking=True,
                    title="Request body schema removed",
                    detail=f"{method} {path} no longer documents a request body.",
                    location=f"{location_base} requestBody",
                    evidence="requestBody schema removed",
                    method=method,
                    path=path,
                    old_value=old_op.request_schema,
                    suggestion="Confirm the server still accepts the existing request payload.",
                )
            elif old_op.request_schema is not None and new_op.request_schema is not None:
                if old_media and new_media and old_media != new_media:
                    collector.emit(
                        rule="request.media_type_changed",
                        kind="request_media_type_changed",
                        severity="medium",
                        breaking=True,
                        title="Request media type changed",
                        detail=f"{method} {path} request media type changed from {old_media} to {new_media}.",
                        location=f"{location_base} requestBody.content",
                        evidence=f"old={old_media} new={new_media}",
                        method=method,
                        path=path,
                        old_value=old_media,
                        new_value=new_media,
                        suggestion="Accept both media types until consumers migrate.",
                        schema_pointer=f"{_operation_pointer(path, method)}/requestBody",
                    )
                if new_op.request_required and not old_op.request_required:
                    collector.emit(
                        rule="request.body.required_changed",
                        kind="request_body_required_changed",
                        severity="high",
                        breaking=True,
                        title="Request body became required",
                        detail=f"{method} {path} request body is now required.",
                        location=f"{location_base} requestBody.required",
                        evidence="old required=false new required=true",
                        method=method,
                        path=path,
                        old_value=False,
                        new_value=True,
                        suggestion="Keep the body optional during deprecation.",
                        schema_pointer=f"{_operation_pointer(path, method)}/requestBody",
                    )
                _compare_schema(
                    collector,
                    old_op.request_schema,
                    new_op.request_schema,
                    context="request",
                    method=method,
                    path=path,
                    location=f"{location_base} requestBody",
                    pointer=_schema_pointer_for_request(new.raw, new_op),
                )
            old_codes = set(old_op.responses)
            new_codes = set(new_op.responses)
            for code in sorted(old_codes - new_codes):
                collector.emit(
                    rule="response.code.removed",
                    kind="response_code_removed",
                    severity="high",
                    breaking=True,
                    title=f"Response code removed: {code}",
                    detail=f"{method} {path} no longer documents response {code}.",
                    location=f"{location_base} responses.{code}",
                    evidence=f"removed response {code}",
                    method=method,
                    path=path,
                    old_value=code,
                    new_value=None,
                    suggestion=f"Keep returning {code} until consumers handle the replacement.",
                    schema_pointer=f"{_operation_pointer(path, method)}/responses",
                    parameter=code,
                )
            for code in sorted(new_codes - old_codes):
                collector.emit(
                    rule="response.code.added",
                    kind="response_code_added",
                    severity="info",
                    breaking=False,
                    title=f"Response code added: {code}",
                    detail=f"{method} {path} now documents response {code}.",
                    location=f"{location_base} responses.{code}",
                    evidence=f"added response {code}",
                    method=method,
                    path=path,
                    new_value=code,
                )
            for code in sorted(old_codes & new_codes):
                _compare_schema(
                    collector,
                    old_op.responses[code],
                    new_op.responses[code],
                    context="response",
                    method=method,
                    path=path,
                    location=f"{location_base} responses.{code}",
                    pointer=_schema_pointer_for_response(new.raw, new_op, code),
                )
            _compare_security(collector, old_op, new_op)


def _compare_global(
    collector: DiffCollector, old: LoadedSpec, new: LoadedSpec
) -> None:
    if old.version != new.version:
        collector.emit(
            rule="info.version_changed",
            kind="version_changed",
            severity="info",
            breaking=False,
            title=f"API version changed: {old.version} -> {new.version}",
            detail="The declared info.version changed. This is informational; endpoint changes are evaluated separately.",
            location="info.version",
            evidence=f"{old.version} -> {new.version}",
            old_value=old.version,
            new_value=new.version,
        )
    if old.servers != new.servers:
        severity = "high" if old.servers and new.servers else "medium"
        collector.emit(
            rule="servers.changed",
            kind="servers_changed",
            severity=severity,
            breaking=bool(old.servers),
            title="Server base URL changed",
            detail="The servers array changed; hard-coded base URLs in consumers may break.",
            location="servers",
            evidence=f"old={compact_json(old.servers)} new={compact_json(new.servers)}",
            old_value=old.servers,
            new_value=new.servers,
            suggestion="Keep the previous base URL redirecting to the new host through the migration window.",
        )
    old_schemes = ((old.raw.get("components") or {}).get("securitySchemes") or {})
    new_schemes = ((new.raw.get("components") or {}).get("securitySchemes") or {})
    for name in sorted(set(old_schemes) - set(new_schemes)):
        collector.emit(
            rule="security.scheme_removed",
            kind="security_scheme_removed",
            severity="high",
            breaking=True,
            title=f"Security scheme removed: {name}",
            detail=f"Authentication scheme '{name}' was removed from components.securitySchemes.",
            location=f"components.securitySchemes.{name}",
            evidence=compact_json(old_schemes[name]),
            old_value=old_schemes[name],
            new_value=None,
            suggestion="Keep the old scheme accepted until all consumers have migrated.",
        )
    for name in sorted(set(new_schemes) - set(old_schemes)):
        collector.emit(
            rule="security.scheme_added",
            kind="security_scheme_added",
            severity="info",
            breaking=False,
            title=f"Security scheme added: {name}",
            detail=f"A new security scheme '{name}' was added.",
            location=f"components.securitySchemes.{name}",
            evidence=compact_json(new_schemes[name]),
            new_value=new_schemes[name],
        )


def diff_specs(old: LoadedSpec, new: LoadedSpec, max_findings: int = 250) -> list[Finding]:
    collector = DiffCollector(cap=max_findings)
    _compare_global(collector, old, new)
    _compare_operations(collector, old, new)
    return collector.finalize()


def count_endpoint_changes(
    old: LoadedSpec, new: LoadedSpec, findings: list[Finding]
) -> tuple[int, int, int]:
    removed = len([f for f in findings if f.kind == "endpoint_removed"])
    added = len([f for f in findings if f.kind == "endpoint_added"])
    affected = {(f.method, f.path) for f in findings if f.method and f.path}
    return added, removed, len(affected)


def clone_spec(spec: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(spec)
