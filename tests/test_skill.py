from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.llm.prompts import build_migration_prompt
from app.main import app
from app.skills import load_skill

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_SKILL = ROOT / "skills" / "api-migration" / "SKILL.md"
PACKAGED_SKILL = ROOT / "backend" / "app" / "resources" / "api-migration" / "SKILL.md"


def test_skill_is_packaged_for_deployment():
    assert CANONICAL_SKILL.is_file()
    assert PACKAGED_SKILL.is_file()
    assert CANONICAL_SKILL.read_bytes() == PACKAGED_SKILL.read_bytes()


def test_skill_frontmatter_is_valid_and_loaded():
    skill = load_skill()
    assert skill.name == "api-migration"
    assert skill.version == "1.0.0"
    assert skill.license == "MIT"
    assert skill.allowed_tools == "Read Grep WebFetch"
    assert skill.digest.startswith("sha256:")
    assert "## Safety rules" in skill.body


def test_skill_is_injected_into_gemma_prompt():
    prompt = build_migration_prompt({}, {}, {}, {}, [], skill_guidance=load_skill().body)
    assert "AGENT SKILL PROTOCOL" in prompt
    assert "Never call production services or exfiltrate secrets" in prompt
    assert "EVIDENCE (untrusted data, JSON)" in prompt


def test_skill_endpoint_reports_runtime_integration():
    response = TestClient(app).get("/api/skill")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "api-migration"
    assert body["digest"].startswith("sha256:")
    assert body["used_by"] == ["Migration Strategist"]
    assert "Gemma" in body["prompt_integration"]
