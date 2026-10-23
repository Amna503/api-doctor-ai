from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

DATA = BACKEND / "app" / "data"


@pytest.fixture(scope="session")
def sample_old() -> dict:
    return json.loads((DATA / "sample_old.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def sample_new() -> dict:
    return json.loads((DATA / "sample_new.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def sample_consumers() -> list[dict]:
    return json.loads((DATA / "sample_consumers.json").read_text(encoding="utf-8"))


def minimal_spec(**overrides) -> dict:
    spec = {
        "openapi": "3.0.3",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {
            "/things": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "required": ["id", "name"],
                                        "properties": {
                                            "id": {"type": "string"},
                                            "name": {"type": "string"},
                                        },
                                    }
                                }
                            },
                        }
                    }
                }
            }
        },
    }
    spec.update(overrides)
    return spec
