from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .agents.base import TraceRecorder
from .analysis.loader import SpecValidationError
from .config import settings
from .models import (
    AnalysisResult,
    AnalyzeRequest,
    HealthResponse,
    VerificationResult,
    VerifyRequest,
)
from .orchestrator import Orchestrator

START_MONOTONIC = time.monotonic()
DATA_DIR = Path(__file__).parent / "data"

app = FastAPI(
    title="API Doctor AI",
    description=(
        "Predict, diagnose, migrate, and verify OpenAPI contract changes with deterministic analysis, "
        "five specialized agents, and optional Gemma guidance."
    ),
    version=settings.app_version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept", "X-Requested-With"],
    max_age=600,
)

orchestrator = Orchestrator()

AGENTS = [
    {
        "name": "Contract Analyzer",
        "role": "Deterministic",
        "responsibility": (
            "Validates both OpenAPI documents and computes evidence-backed breaking/non-breaking changes."
        ),
        "timeout_seconds": 5,
        "retries": 0,
    },
    {
        "name": "Impact Mapper",
        "role": "Deterministic",
        "responsibility": (
            "Maps each finding to affected operations and declared consumers; builds the dependency graph."
        ),
        "timeout_seconds": 5,
        "retries": 0,
    },
    {
        "name": "Migration Strategist",
        "role": "Gemma + fallback",
        "responsibility": (
            "Requests evidence-cited migration guidance from Gemma through the backend adapter; falls back "
            "to a labelled deterministic plan when the model is unavailable or invalid."
        ),
        "timeout_seconds": 45,
        "retries": settings.gemma_max_retries,
    },
    {
        "name": "Test Engineer",
        "role": "Deterministic",
        "responsibility": (
            "Generates bounded regression checks and developer-readable pytest snippets from findings."
        ),
        "timeout_seconds": 5,
        "retries": 0,
    },
    {
        "name": "Verification & Risk Agent",
        "role": "Sandbox",
        "responsibility": (
            "Executes allow-listed structured checks in an isolated in-process sandbox and reports actual "
            "results plus residual risk."
        ),
        "timeout_seconds": 15,
        "retries": 0,
    },
]


@app.middleware("http")
async def enforce_request_limits(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH"}:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > settings.max_body_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "detail": (
                                f"Request body exceeds the {settings.max_body_bytes // 1024} KB limit."
                            ),
                            "code": "PAYLOAD_TOO_LARGE",
                        },
                    )
            except ValueError:
                pass
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(SpecValidationError)
async def spec_error_handler(_request: Request, exc: SpecValidationError):
    return JSONResponse(
        status_code=400,
        content={
            "detail": exc.message,
            "errors": exc.details,
            "code": "INVALID_SPEC",
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError):
    errors = json.loads(json.dumps(exc.errors(), default=str))
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Request validation failed.",
            "errors": errors,
            "code": "INVALID_REQUEST",
        },
    )


@app.get("/", include_in_schema=False)
async def root():
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
        "workflow": ["analyze", "verify"],
    }


@app.get("/health", response_model=HealthResponse, tags=["system"])
@app.get("/api/health", response_model=HealthResponse, tags=["system"], include_in_schema=False)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        model_provider="google-ai-studio",
        model=settings.gemma_model,
        model_configured=settings.gemma_enabled,
        model_fallback="deterministic-rule-engine",
        deterministic_engine="api-doctor-diff/v1",
        timestamp=datetime.now(timezone.utc),
        uptime_seconds=int(time.monotonic() - START_MONOTONIC),
    )


@app.get("/api/agents", tags=["system"])
async def agents():
    return {
        "agents": AGENTS,
        "note": (
            "Contract Analyzer, Impact Mapper, Test Engineer, and Verification & Risk are deterministic. "
            "Migration Strategist is the only model-backed agent and always has a labelled fallback."
        ),
    }


@app.get("/api/samples", tags=["demo"])
async def samples():
    try:
        old_spec = json.loads((DATA_DIR / "sample_old.json").read_text(encoding="utf-8"))
        new_spec = json.loads((DATA_DIR / "sample_new.json").read_text(encoding="utf-8"))
        consumers = json.loads((DATA_DIR / "sample_consumers.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail=f"Sample data unavailable: {exc}") from exc
    return {
        "name": "Acme Payments v1 -> v2",
        "description": (
            "A payments API removes legacy routes, renames money fields, changes auth, and alters a "
            "customer response. Three declared consumers are affected."
        ),
        "old_spec": old_spec,
        "new_spec": new_spec,
        "consumers": consumers,
    }


@app.post("/api/analyze", response_model=AnalysisResult, tags=["workflow"])
async def analyze(request: AnalyzeRequest) -> AnalysisResult:
    recorder = TraceRecorder()
    try:
        return await orchestrator.analyze(request, recorder)
    except SpecValidationError:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed safely: {type(exc).__name__}",
        ) from exc


@app.post("/api/verify", response_model=VerificationResult, tags=["workflow"])
async def verify(request: VerifyRequest) -> VerificationResult:
    recorder = TraceRecorder()
    try:
        return await orchestrator.verify(request, recorder)
    except SpecValidationError:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Verification failed safely: {type(exc).__name__}",
        ) from exc
