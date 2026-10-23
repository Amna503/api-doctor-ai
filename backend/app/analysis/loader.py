from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from typing import Any

HTTP_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")
HTTP_METHODS_UPPER = tuple(method.upper() for method in HTTP_METHODS)


class SpecValidationError(ValueError):
    def __init__(self, message: str, details: list[str] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or []


def _json_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "string"


def resolve_ref(spec: dict[str, Any], node: Any, _seen: set[str] | None = None) -> Any:
    """Resolve local OpenAPI $refs. External refs are intentionally not fetched."""
    if not isinstance(node, dict):
        return node
    seen = set(_seen or set())
    if "$ref" in node:
        ref = node["$ref"]
        if not isinstance(ref, str):
            return node
        if not ref.startswith("#/"):
            raise SpecValidationError(f"External $ref is not supported: {ref}")
        if ref in seen:
            return {"type": "object", "x-circular-ref": True, "description": "circular reference"}
        target: Any = spec
        for token in ref[2:].split("/"):
            token = token.replace("~1", "/").replace("~0", "~")
            if not isinstance(target, dict) or token not in target:
                raise SpecValidationError(f"Unresolvable $ref: {ref}")
            target = target[token]
        resolved = resolve_ref(spec, target, seen | {ref})
        if isinstance(resolved, dict):
            siblings = {k: v for k, v in node.items() if k != "$ref"}
            if siblings:
                resolved = {**resolved, **resolve_ref(spec, siblings, seen)}
        return resolved
    return node


def resolve_schema(spec: dict[str, Any], schema: Any, depth: int = 0) -> Any:
    if depth > 12 or not isinstance(schema, dict):
        return schema
    schema = resolve_ref(spec, schema)
    if not isinstance(schema, dict):
        return schema
    if "allOf" in schema and isinstance(schema["allOf"], list):
        merged: dict[str, Any] = {}
        required: list[str] = []
        properties: dict[str, Any] = {}
        for part in schema["allOf"]:
            part = resolve_schema(spec, part, depth + 1)
            if not isinstance(part, dict):
                continue
            merged.update({k: v for k, v in part.items() if k not in {"properties", "required"}})
            properties.update(part.get("properties") or {})
            required.extend(part.get("required") or [])
        merged.update({k: v for k, v in schema.items() if k != "allOf"})
        if "properties" in schema:
            properties.update(schema.get("properties") or {})
        if properties:
            merged["properties"] = properties
        if required or schema.get("required"):
            merged["required"] = sorted(set(required + list(schema.get("required") or [])))
        schema = merged
    out = copy.deepcopy(schema)
    if isinstance(out.get("properties"), dict):
        out["properties"] = {
            key: resolve_schema(spec, value, depth + 1)
            for key, value in out["properties"].items()
        }
    if isinstance(out.get("items"), dict):
        out["items"] = resolve_schema(spec, out["items"], depth + 1)
    for key in ("oneOf", "anyOf", "allOf"):
        if isinstance(out.get(key), list):
            out[key] = [resolve_schema(spec, item, depth + 1) for item in out[key]]
    if isinstance(out.get("additionalProperties"), dict):
        out["additionalProperties"] = resolve_schema(spec, out["additionalProperties"], depth + 1)
    return out


def schema_types(schema: dict[str, Any]) -> list[str]:
    raw = schema.get("type")
    if isinstance(raw, list):
        types = [str(item) for item in raw]
    elif isinstance(raw, str):
        types = [raw]
    else:
        if "properties" in schema:
            types = ["object"]
        elif "items" in schema:
            types = ["array"]
        else:
            types = []
    if schema.get("nullable") is True and "null" not in types:
        types.append("null")
    return types


def _pick_content_schema(content: Any) -> dict[str, Any] | None:
    if not isinstance(content, dict) or not content:
        return None
    media = content.get("application/json")
    if media is None:
        for key in content:
            if "json" in key:
                media = content[key]
                break
    if media is None:
        media = next(iter(content.values()))
    if isinstance(media, dict) and isinstance(media.get("schema"), dict):
        return media["schema"]
    return None


def _media_type(content: Any) -> str | None:
    if not isinstance(content, dict) or not content:
        return None
    if "application/json" in content:
        return "application/json"
    for key in content:
        if "json" in key:
            return key
    return str(next(iter(content.keys())))


@dataclass
class OperationView:
    method: str
    path: str
    operation: dict[str, Any]
    parameters: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    request_schema: dict[str, Any] | None = None
    request_required: bool = False
    request_media_type: str | None = None
    responses: dict[str, dict[str, Any] | None] = field(default_factory=dict)
    security: list[dict[str, Any]] = field(default_factory=list)
    deprecated: bool = False

    @property
    def key(self) -> str:
        return f"{self.method.upper()} {self.path}"


@dataclass
class LoadedSpec:
    raw: dict[str, Any]
    title: str
    version: str
    openapi: str
    servers: list[str]
    operations: dict[str, OperationView]
    path_item_methods: dict[str, set[str]]

    @property
    def endpoint_keys(self) -> list[str]:
        return sorted(self.operations.keys(), key=lambda item: (item.split(" ", 1)[1], item))

    def meta(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "version": self.version,
            "openapi": self.openapi,
            "endpoint_count": len(self.operations),
            "operations": self.endpoint_keys,
            "servers": self.servers,
        }


def _collect_parameters(spec: dict[str, Any], path_item: dict[str, Any], operation: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    merged = list(path_item.get("parameters") or []) + list(operation.get("parameters") or [])
    for raw in merged:
        if not isinstance(raw, dict):
            continue
        param = resolve_ref(spec, raw)
        if not isinstance(param, dict):
            continue
        name = str(param.get("name", ""))
        location = str(param.get("in", ""))
        if name and location:
            result[(name, location)] = param
    return result


def load_spec(raw: Any, label: str = "specification") -> LoadedSpec:
    if not isinstance(raw, dict):
        raise SpecValidationError(f"The {label} must be a JSON object.")
    if not raw:
        raise SpecValidationError(f"The {label} is empty.")
    version = raw.get("openapi")
    if version is None:
        if str(raw.get("swagger", "")).startswith("2"):
            raise SpecValidationError(
                f"The {label} is Swagger 2.0. Convert it to OpenAPI 3.0/3.1 before analysis."
            )
        raise SpecValidationError(
            f"The {label} is missing the 'openapi' version field (expected 3.0.x or 3.1.x)."
        )
    if not isinstance(version, str) or not (version.startswith("3.0") or version.startswith("3.1")):
        raise SpecValidationError(
            f"The {label} declares unsupported OpenAPI version '{version}'. Supported: 3.0.x and 3.1.x."
        )
    paths = raw.get("paths")
    if not isinstance(paths, dict) or not paths:
        raise SpecValidationError(f"The {label} must contain a non-empty 'paths' object.")
    if len(paths) > 300:
        raise SpecValidationError(f"The {label} has too many paths (max 300).")

    info = raw.get("info") if isinstance(raw.get("info"), dict) else {}
    servers: list[str] = []
    for server in raw.get("servers") or []:
        if isinstance(server, dict) and server.get("url"):
            servers.append(str(server["url"]))

    operations: dict[str, OperationView] = {}
    path_item_methods: dict[str, set[str]] = {}
    for path, raw_path_item in paths.items():
        if not isinstance(path, str) or not path.startswith("/"):
            if isinstance(path, str) and path.startswith("x-"):
                continue
            raise SpecValidationError(f"The {label} contains an invalid path key: {path!r}")
        path_item = resolve_ref(raw, raw_path_item)
        if not isinstance(path_item, dict):
            raise SpecValidationError(f"Path item for {path} must be an object.")
        methods: set[str] = set()
        for method in HTTP_METHODS:
            operation = path_item.get(method)
            if not isinstance(operation, dict):
                continue
            methods.add(method.upper())
            parameters = _collect_parameters(raw, path_item, operation)
            request_schema = None
            request_required = False
            request_media_type = None
            body = operation.get("requestBody")
            if isinstance(body, dict):
                body = resolve_ref(raw, body)
                if isinstance(body, dict):
                    request_required = bool(body.get("required", False))
                    content = body.get("content")
                    request_schema = _pick_content_schema(content)
                    request_media_type = _media_type(content)
                    if request_schema is not None:
                        request_schema = resolve_schema(raw, request_schema)
            responses: dict[str, dict[str, Any] | None] = {}
            for code, raw_response in (operation.get("responses") or {}).items():
                response = resolve_ref(raw, raw_response)
                schema = None
                if isinstance(response, dict):
                    schema = _pick_content_schema(response.get("content"))
                    if schema is not None:
                        schema = resolve_schema(raw, schema)
                responses[str(code)] = schema
            security = operation.get("security")
            if security is None:
                security = raw.get("security") or []
            security = [
                entry for entry in security if isinstance(entry, dict)
            ] if isinstance(security, list) else []
            key = f"{method.upper()} {path}"
            operations[key] = OperationView(
                method=method.upper(),
                path=path,
                operation=operation,
                parameters=parameters,
                request_schema=request_schema,
                request_required=request_required,
                request_media_type=request_media_type,
                responses=responses,
                security=security,
                deprecated=bool(operation.get("deprecated", False)),
            )
        if methods:
            path_item_methods[path] = methods
        if len(operations) > 1000:
            raise SpecValidationError(f"The {label} has too many operations (max 1000).")

    if not operations:
        raise SpecValidationError(f"The {label} does not contain any HTTP operations.")

    return LoadedSpec(
        raw=raw,
        title=str(info.get("title") or "Untitled API"),
        version=str(info.get("version") or "unspecified"),
        openapi=version,
        servers=servers,
        operations=operations,
        path_item_methods=path_item_methods,
    )


def normalize_for_validation(schema: Any, depth: int = 0) -> Any:
    if depth > 15 or not isinstance(schema, dict):
        return schema
    out: dict[str, Any] = {}
    for key, value in schema.items():
        if key in {"example", "examples", "xml", "discriminator", "readOnly", "writeOnly", "deprecated", "externalDocs"}:
            continue
        out[key] = copy.deepcopy(value)
    if out.get("nullable") is True:
        out.pop("nullable", None)
        types = schema_types(out)
        if types and "null" not in types:
            out["type"] = types + ["null"]
    properties = out.get("properties")
    if isinstance(properties, dict):
        out["properties"] = {
            key: normalize_for_validation(value, depth + 1)
            for key, value in properties.items()
        }
    if isinstance(out.get("items"), dict):
        out["items"] = normalize_for_validation(out["items"], depth + 1)
    for key in ("oneOf", "anyOf", "allOf"):
        if isinstance(out.get(key), list):
            out[key] = [normalize_for_validation(item, depth + 1) for item in out[key]]
    if isinstance(out.get("additionalProperties"), dict):
        out["additionalProperties"] = normalize_for_validation(
            out["additionalProperties"], depth + 1
        )
    return out


def build_example(schema: Any, include_optional: bool = True, depth: int = 0, name: str = "value") -> Any:
    """Create a deterministic example payload from a JSON Schema."""
    if depth > 8 or not isinstance(schema, dict):
        return None
    if "example" in schema:
        return copy.deepcopy(schema["example"])
    if "examples" in schema and isinstance(schema["examples"], list) and schema["examples"]:
        return copy.deepcopy(schema["examples"][0])
    if "default" in schema:
        return copy.deepcopy(schema["default"])
    if "const" in schema:
        return copy.deepcopy(schema["const"])
    if isinstance(schema.get("enum"), list) and schema["enum"]:
        return copy.deepcopy(schema["enum"][0])
    for combinator in ("oneOf", "anyOf"):
        options = schema.get(combinator)
        if isinstance(options, list) and options:
            return build_example(options[0], include_optional, depth + 1, name)
    types = [t for t in schema_types(schema) if t != "null"]
    type_name = types[0] if types else ("object" if "properties" in schema else "string")
    if type_name == "object":
        properties = schema.get("properties") or {}
        required = set(schema.get("required") or [])
        out: dict[str, Any] = {}
        for prop_name, prop_schema in properties.items():
            if not include_optional and prop_name not in required:
                continue
            out[prop_name] = build_example(
                prop_schema, include_optional, depth + 1, prop_name
            )
            if len(out) >= 16:
                break
        return out
    if type_name == "array":
        item_schema = schema.get("items") or {}
        return [build_example(item_schema, include_optional, depth + 1, name)]
    if type_name == "integer":
        return int(schema.get("minimum", 1)) if isinstance(schema.get("minimum"), (int, float)) else 1
    if type_name == "number":
        return float(schema.get("minimum", 1.0)) if isinstance(schema.get("minimum"), (int, float)) else 1.0
    if type_name == "boolean":
        return True
    if type_name == "null":
        return None
    fmt = schema.get("format")
    if fmt == "date-time":
        return "2026-01-15T12:00:00Z"
    if fmt == "date":
        return "2026-01-15"
    if fmt == "uuid":
        return "123e4567-e89b-12d3-a456-426614174000"
    if fmt == "email":
        return "developer@example.com"
    if fmt == "uri":
        return "https://example.com/resource"
    if name:
        return str(name).replace("_", "-")
    return "string"


def compact_json(value: Any, limit: int = 600) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    except (TypeError, ValueError):
        text = str(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."
