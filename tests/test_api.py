from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint_reports_model_configuration():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["deterministic_engine"] == "api-doctor-diff/v1"
    assert body["model_fallback"] == "deterministic-rule-engine"
    assert "model_configured" in body


def test_root_and_agents_metadata():
    root = client.get("/")
    assert root.status_code == 200
    agents = client.get("/api/agents").json()["agents"]
    assert len(agents) == 5
    assert {agent["name"] for agent in agents} == {
        "Contract Analyzer",
        "Impact Mapper",
        "Migration Strategist",
        "Test Engineer",
        "Verification & Risk Agent",
    }


def test_samples_are_available():
    response = client.get("/api/samples")
    assert response.status_code == 200
    body = response.json()
    assert body["old_spec"]["openapi"] == "3.0.3"
    assert body["new_spec"]["openapi"] == "3.0.3"
    assert len(body["consumers"]) == 3


def test_analyze_sample_workflow(sample_old, sample_new, sample_consumers):
    response = client.post(
        "/api/analyze",
        json={
            "old_spec": sample_old,
            "new_spec": sample_new,
            "consumers": sample_consumers,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["summary"]["breaking_changes"] >= 8
    assert body["summary"]["endpoints_removed"] == 5
    assert len(body["impact"]["consumers"]) == 3
    assert len(body["migration"]["steps"]) > 0
    assert len(body["tests"]["tests"]) > 0
    assert body["risk"]["verified"] is False
    assert any(trace["agent"] == "Migration Strategist" for trace in body["traces"])
    assert all(finding["source"] == "deterministic" for finding in body["findings"])


def test_verify_sample_workflow_reports_actual_failures(sample_old, sample_new, sample_consumers):
    response = client.post(
        "/api/verify",
        json={
            "old_spec": sample_old,
            "new_spec": sample_new,
            "consumers": sample_consumers,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] >= 6
    assert body["failed"] >= 5
    assert body["risk"]["verified"] is True
    assert body["risk"]["status"] == "unresolved_risks"
    assert body["passed"] + body["failed"] + body["skipped"] == body["total"]


def test_compatibility_patch_verification_reduces_risk(sample_old, sample_new, sample_consumers):
    response = client.post(
        "/api/verify",
        json={
            "old_spec": sample_old,
            "new_spec": sample_new,
            "consumers": sample_consumers,
            "apply_compatibility_patch": True,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["compatibility_patch"]["applied"] is True
    assert body["compatibility_patch"]["changes"]
    assert body["compatibility_patch"]["residual_breaking_changes"] < 9
    assert body["passed"] >= body["failed"]


def test_invalid_spec_returns_actionable_400():
    response = client.post(
        "/api/analyze",
        json={"old_spec": {"openapi": "3.0.3"}, "new_spec": {"openapi": "3.0.3", "paths": {}}},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "INVALID_SPEC"
    assert "paths" in body["detail"]


def test_invalid_consumer_endpoint_returns_422(sample_old, sample_new):
    response = client.post(
        "/api/analyze",
        json={
            "old_spec": sample_old,
            "new_spec": sample_new,
            "consumers": [{"name": "Bad", "endpoints": ["not-a-method /x"]}],
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_REQUEST"


def test_oversized_body_is_rejected():
    payload = "x" * (2 * 1024 * 1024 + 500)
    response = client.post(
        "/api/analyze",
        content=payload,
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["code"] == "PAYLOAD_TOO_LARGE"


def test_cors_allows_local_frontend():
    response = client.options(
        "/api/analyze",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code in {200, 204}
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
