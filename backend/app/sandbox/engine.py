from __future__ import annotations

import time
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from ..analysis.loader import (
    LoadedSpec,
    OperationView,
    build_example,
    normalize_for_validation,
    schema_types,
)
from ..models import GeneratedTest, TestResult


def _incompatible_types(old_types: list[str], new_types: list[str]) -> bool:
    old_set = {item for item in old_types if item != "null"}
    new_set = {item for item in new_types if item != "null"}
    if not old_set or not new_set:
        return False
    if old_set <= new_set:
        return False
    if old_set == {"integer"} and new_set == {"number"}:
        return False
    return True


def schema_compatibility(old_schema: Any, new_schema: Any, location: str = "$", depth: int = 0) -> list[str]:
    if depth > 10:
        return []
    if new_schema is None:
        return [f"{location}: new contract no longer declares this schema"]
    if not isinstance(old_schema, dict) or not isinstance(new_schema, dict):
        return []
    issues: list[str] = []
    old_types = schema_types(old_schema)
    new_types = schema_types(new_schema)
    if _incompatible_types(old_types, new_types):
        issues.append(
            f"{location}: type {old_types or 'unspecified'} is incompatible with {new_types or 'unspecified'}"
        )
        return issues
    if "null" in old_types and "null" not in new_types:
        issues.append(f"{location}: null values are no longer accepted")
    old_enum = old_schema.get("enum") if isinstance(old_schema.get("enum"), list) else None
    new_enum = new_schema.get("enum") if isinstance(new_schema.get("enum"), list) else None
    if old_enum is not None and new_enum is not None:
        removed = [value for value in old_enum if value not in new_enum]
        if removed:
            issues.append(f"{location}: enum values removed {removed}")
    old_types_clean = [item for item in old_types if item != "null"]
    new_types_clean = [item for item in new_types if item != "null"]
    if "object" in old_types_clean and "object" in new_types_clean:
        old_props = old_schema.get("properties") if isinstance(old_schema.get("properties"), dict) else {}
        new_props = new_schema.get("properties") if isinstance(new_schema.get("properties"), dict) else {}
        for name in sorted(set(old_props) - set(new_props)):
            issues.append(f"{location}.{name}: field removed from new response schema")
        for name in sorted(set(old_props) & set(new_props)):
            issues.extend(
                schema_compatibility(
                    old_props[name],
                    new_props[name],
                    f"{location}.{name}",
                    depth + 1,
                )
            )
    if "array" in old_types_clean and "array" in new_types_clean:
        if isinstance(old_schema.get("items"), dict) and isinstance(new_schema.get("items"), dict):
            issues.extend(
                schema_compatibility(
                    old_schema["items"],
                    new_schema["items"],
                    f"{location}[]",
                    depth + 1,
                )
            )
    return issues[:12]


def _validate_value(schema: dict[str, Any], value: Any) -> list[str]:
    try:
        normalized = normalize_for_validation(schema)
        Draft202012Validator.check_schema(normalized)
        validator = Draft202012Validator(normalized)
        errors = sorted(validator.iter_errors(value), key=lambda error: list(error.path))
    except SchemaError as exc:
        return [f"invalid target schema: {exc.message}"]
    except Exception as exc:  # defensive: sandbox must never crash a verification run
        return [f"schema validation unavailable: {type(exc).__name__}: {exc}"]
    messages: list[str] = []
    for error in errors[:6]:
        path = "$"
        if error.path:
            path = "$." + ".".join(str(item) for item in error.path)
        messages.append(f"{path}: {error.message}")
    return messages


def _legacy_path_value(param: dict[str, Any]) -> str:
    example = build_example(param.get("schema") if isinstance(param.get("schema"), dict) else {})
    if example is None:
        example = "sample"
    if isinstance(example, (dict, list)):
        return "sample"
    return str(example)


def _legacy_request_checks(
    old_op: OperationView, new_op: OperationView
) -> tuple[list[str], dict[str, Any]]:
    failures: list[str] = []
    provided_params: dict[tuple[str, str], Any] = {}
    path_values: dict[str, Any] = {}
    for (name, where), param in old_op.parameters.items():
        value = build_example(
            param.get("schema") if isinstance(param.get("schema"), dict) else {},
            name=name,
        )
        if where == "path":
            path_values[name] = value
        provided_params[(name, where)] = value

    request_path = old_op.path
    for name, value in path_values.items():
        request_path = request_path.replace("{" + name + "}", _legacy_path_value({"schema": {"type": "string", "example": value}}))

    if new_op.path != old_op.path:
        failures.append(f"path changed from {old_op.path} to {new_op.path}")
    for (name, where), param in new_op.parameters.items():
        required = bool(param.get("required", False)) or where == "path"
        if not required:
            continue
        if (name, where) not in provided_params:
            failures.append(f"new required {where} parameter '{name}' is missing from the legacy request")
            continue
        schema = param.get("schema") if isinstance(param.get("schema"), dict) else {}
        if schema:
            failures.extend(
                f"parameter {where}.{name}: {message}"
                for message in _validate_value(schema, provided_params[(name, where)])
            )

    legacy_body = (
        build_example(old_op.request_schema, include_optional=True)
        if old_op.request_schema is not None
        else None
    )
    if new_op.request_required and legacy_body is None:
        failures.append("new contract requires a request body, legacy request has none")
    if new_op.request_schema is not None and legacy_body is not None:
        failures.extend(
            f"request body: {message}"
            for message in _validate_value(new_op.request_schema, legacy_body)
        )
    details = {
        "method": old_op.method,
        "path": request_path,
        "params": {
            f"{where}.{name}": value for (name, where), value in provided_params.items()
        },
        "body_present": legacy_body is not None,
        "body_keys": sorted(legacy_body.keys()) if isinstance(legacy_body, dict) else None,
    }
    return failures, details


def _response_failures(
    old_op: OperationView, new_op: OperationView, code: str
) -> tuple[list[str], str]:
    old_schema = old_op.responses.get(code)
    new_schema = new_op.responses.get(code)
    if new_schema is None:
        return [f"response {code} is no longer documented"], f"response {code} missing"
    issues = schema_compatibility(old_schema, new_schema)
    return issues, f"checked response {code}"


def execute_test(
    test: GeneratedTest, old: LoadedSpec, new: LoadedSpec
) -> TestResult:
    started = time.perf_counter()
    failures: list[str] = []
    evidence: list[str] = []
    actual = ""

    old_op = old.operations.get(f"{test.method} {test.path}")
    new_op = new.operations.get(f"{test.method} {test.path}")

    if test.type == "endpoint_available":
        if new_op is None:
            failures.append(f"{test.method} {test.path} does not exist in the target contract")
        else:
            evidence.append(f"{test.method} {test.path} exists with {len(new_op.parameters)} parameters")
        actual = "endpoint present" if new_op is not None else "endpoint absent (404/405 for legacy callers)"
    elif test.type == "legacy_request":
        if old_op is None:
            failures.append("legacy operation not found in old contract")
        elif new_op is None:
            failures.append(f"{test.method} {test.path} was removed")
        else:
            request_failures, details = _legacy_request_checks(old_op, new_op)
            failures.extend(request_failures)
            evidence.append(
                f"legacy request {details['method']} {details['path']} "
                f"params={details['params']} body_keys={details['body_keys']}"
            )
            actual = (
                "legacy request accepted by target contract"
                if not request_failures
                else "legacy request rejected by target contract"
            )
    elif test.type == "response_contract":
        code = str(test.check.get("code") or "200")
        if old_op is None:
            failures.append("legacy operation not found in old contract")
        elif new_op is None:
            failures.append(f"{test.method} {test.path} was removed")
        else:
            issues, detail = _response_failures(old_op, new_op, code)
            failures.extend(issues)
            evidence.append(detail)
            actual = (
                f"old response {code} remains structurally compatible"
                if not issues
                else f"old response {code} is no longer compatible"
            )
    else:
        failures.append(f"unsupported test type: {test.type}")

    duration_ms = max(0, int((time.perf_counter() - started) * 1000))
    status = "passed" if not failures else "failed"
    return TestResult(
        test_id=test.id,
        name=test.name,
        type=test.type,
        method=test.method,
        path=test.path,
        finding_ids=test.finding_ids,
        status=status,
        expected=test.expected,
        actual=f"{actual}. " + (" | ".join(failures) if failures else "All assertions passed."),
        evidence=evidence + failures,
        duration_ms=duration_ms,
    )
