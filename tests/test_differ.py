from __future__ import annotations

import copy

from app.analysis.differ import diff_specs
from app.analysis.loader import load_spec

from conftest import minimal_spec


def run_diff(old: dict, new: dict):
    return diff_specs(load_spec(copy.deepcopy(old)), load_spec(copy.deepcopy(new)))


def test_removed_endpoint_is_critical_breaking():
    old = minimal_spec()
    new = minimal_spec(paths={})
    new["paths"]["/other"] = {"get": {"responses": {"200": {"description": "ok"}}}}
    findings = run_diff(old, new)
    removed = [item for item in findings if item.kind == "endpoint_removed"]
    assert len(removed) == 1
    assert removed[0].severity == "critical"
    assert removed[0].breaking is True
    assert removed[0].path == "/things"


def test_added_endpoint_is_non_breaking():
    old = minimal_spec()
    new = copy.deepcopy(old)
    new["paths"]["/things/{id}"] = {
        "get": {
            "parameters": [
                {"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}
            ],
            "responses": {"200": {"description": "ok"}},
        }
    }
    findings = run_diff(old, new)
    added = [item for item in findings if item.kind == "endpoint_added"]
    assert added
    assert added[0].breaking is False
    assert added[0].severity == "info"


def test_removed_response_field_is_breaking():
    old = minimal_spec()
    new = copy.deepcopy(old)
    del new["paths"]["/things"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["properties"]["name"]
    new["paths"]["/things"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["required"] = ["id"]
    findings = run_diff(old, new)
    removed = [item for item in findings if item.kind == "response_property_removed"]
    assert len(removed) == 1
    assert removed[0].parameter == "name"
    assert removed[0].breaking is True
    assert removed[0].severity == "high"


def test_new_required_request_field_is_breaking():
    old = minimal_spec()
    old["paths"]["/things"]["post"] = {
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                    }
                }
            },
        },
        "responses": {"201": {"description": "created"}},
    }
    new = copy.deepcopy(old)
    schema = new["paths"]["/things"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    schema["required"] = ["name", "owner"]
    schema["properties"]["owner"] = {"type": "string"}
    findings = run_diff(old, new)
    required = [item for item in findings if item.rule == "request.property_required_added"]
    assert len(required) == 1
    assert required[0].parameter == "owner"
    assert required[0].breaking is True


def test_type_change_is_breaking():
    old = minimal_spec()
    new = copy.deepcopy(old)
    new["paths"]["/things"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["properties"]["id"] = {"type": "integer"}
    findings = run_diff(old, new)
    changed = [item for item in findings if item.kind == "response_type_changed"]
    assert changed and changed[0].breaking is True


def test_integer_to_number_widening_is_not_breaking():
    old = minimal_spec()
    old["paths"]["/things"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["properties"]["id"] = {"type": "integer"}
    new = copy.deepcopy(old)
    new["paths"]["/things"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["properties"]["id"] = {"type": "number"}
    findings = run_diff(old, new)
    assert not [item for item in findings if item.breaking]


def test_enum_narrowing_is_breaking():
    old = minimal_spec()
    old["paths"]["/things"]["get"]["parameters"] = [
        {"name": "state", "in": "query", "schema": {"type": "string", "enum": ["a", "b"]}}
    ]
    new = copy.deepcopy(old)
    new["paths"]["/things"]["get"]["parameters"][0]["schema"]["enum"] = ["a"]
    findings = run_diff(old, new)
    narrowed = [item for item in findings if item.kind == "request_enum_narrowed"]
    assert narrowed and narrowed[0].breaking is True


def test_optional_field_addition_is_not_breaking():
    old = minimal_spec()
    new = copy.deepcopy(old)
    new["paths"]["/things"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["properties"]["note"] = {"type": "string"}
    findings = run_diff(old, new)
    added = [item for item in findings if item.kind == "response_property_added"]
    assert added and added[0].breaking is False


def test_required_parameter_addition_is_breaking():
    old = minimal_spec()
    new = copy.deepcopy(old)
    new["paths"]["/things"]["get"]["parameters"] = [
        {"name": "cursor", "in": "query", "required": True, "schema": {"type": "string"}}
    ]
    findings = run_diff(old, new)
    required = [item for item in findings if item.kind == "parameter_added_required"]
    assert required and required[0].breaking is True
    assert required[0].parameter == "cursor"


def test_server_and_security_changes_are_detected():
    old = minimal_spec(servers=[{"url": "https://api.example/v1"}], security=[{"bearerAuth": []}])
    old["components"] = {"securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer"}}}
    new = copy.deepcopy(old)
    new["servers"] = [{"url": "https://api.example/v2"}]
    new["security"] = [{"bearerAuth": [], "oauth2": ["read"]}]
    findings = run_diff(old, new)
    kinds = {item.kind for item in findings}
    assert "servers_changed" in kinds
    assert "security_changed" in kinds
