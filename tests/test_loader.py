from __future__ import annotations

import pytest

from app.analysis.loader import SpecValidationError, load_spec

from conftest import minimal_spec


def test_valid_spec_loads():
    loaded = load_spec(minimal_spec(), "old specification")
    assert loaded.title == "Test API"
    assert loaded.endpoint_keys == ["GET /things"]


def test_missing_openapi_version_is_rejected():
    spec = minimal_spec()
    del spec["openapi"]
    with pytest.raises(SpecValidationError, match="missing the 'openapi'"):
        load_spec(spec)


def test_swagger_2_is_rejected_with_actionable_message():
    spec = minimal_spec(openapi=None, swagger="2.0")
    spec.pop("openapi")
    with pytest.raises(SpecValidationError, match="Swagger 2.0"):
        load_spec(spec)


def test_missing_paths_is_rejected():
    spec = minimal_spec(paths={})
    with pytest.raises(SpecValidationError, match="non-empty 'paths'"):
        load_spec(spec)


def test_external_ref_is_rejected():
    spec = minimal_spec()
    spec["paths"]["/things"]["get"]["responses"]["200"]["content"]["application/json"]["schema"] = {
        "$ref": "https://evil.example/schema.json"
    }
    with pytest.raises(SpecValidationError, match="External \\$ref"):
        load_spec(spec)


def test_non_object_spec_is_rejected():
    with pytest.raises(SpecValidationError, match="JSON object"):
        load_spec(["not", "an", "object"])
