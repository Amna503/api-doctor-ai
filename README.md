# API Doctor AI

**Predict. Diagnose. Migrate. Verify.** — A full-stack OpenAPI breaking-change analyzer that compares two contracts, maps consumer blast radius, generates evidence-cited migration guidance with Google Gemma 4, produces bounded regression tests, and verifies fixes in an isolated sandbox.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![OpenAPI](https://img.shields.io/badge/OpenAPI-3.x-6BA539.svg)](https://spec.openapis.org/oas/latest.html)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.161.1-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19.3.1-61DAFB.svg)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-7.0.2-3178C6.svg)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-8.3.5-646CFF.svg)](https://vitejs.dev/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-4.3.3-38B2AC.svg)](https://tailwindcss.com/)

## Overview

API Doctor AI turns API contract diffs into actionable migration work. It uses **deterministic rules first** (reproducible, evidence-cited), adds **bounded AI guidance** via **Google Gemma 4** when configured, and **executes real checks** in a sandbox to prove whether breaking changes are actually mitigated.

## Key Features

- **Deterministic contract diff** — Finds breaking/non-breaking changes across endpoints, parameters, schemas, security, and servers with evidence strings.
- **Consumer impact mapping** — Correlates changes to declared consumers and builds a 2D/3D dependency topology.
- **AI migration guidance (bounded)** — Gemma 4 generates ordered, evidence-cited migration steps with timeouts, retries, and schema validation. Falls back to a deterministic plan if unavailable.
- **Regression test generation** — Creates bounded checks (endpoint reachability, legacy request acceptance, response contract) tied to findings.
- **Sandbox verification** — Executes checks against the target contract in an isolated simulator; optionally applies a simulated compatibility shim (non-destructive copy) to measure residual risk.
- **Execution traces** — Full agent timeline with status, duration, provider/model, and fallbacks.
- **Live local servers** — Backend and frontend run locally for development.

## Architecture

```text
api-doctor-ai/
├── backend/                # FastAPI app (Python 3.12)
│   ├── app/
│   │   ├── agents/         # 5 specialized agents
│   │   ├── analysis/       # Loader, differ, impact mapper
│   │   ├── llm/            # Gemma adapter + prompts + fallback
│   │   ├── sandbox/        # JSON-Schema engine + compatibility patch
│   │   ├── data/           # Sample specs/consumers
│   │   ├── config.py       # Env/config
│   │   ├── main.py         # FastAPI routes
│   │   ├── models.py       # Pydantic schemas
│   │   └── orchestrator.py # Agent pipeline
│   ├── requirements.txt
│   ├── vercel.json         # Vercel Python config
│   └── .python-version     # 3.12
├── frontend/               # React 19 + Vite + TypeScript + Tailwind v4
│   ├── src/
│   │   ├── components/     # UI panels, graph, traces
│   │   ├── data/           # Sample fixtures
│   │   ├── lib/            # Utilities
│   │   └── App.tsx         # Main app
│   └── package.json
├── skills/
│   └── api-migration/      # Agent Skills Open Standard
│       └── SKILL.md
├── tests/                  # Backend pytest suite (38 tests)
└── README.md
```

## Five Specialized Agents

| Agent | Responsibility | Type |
|---|---|---|
| **Contract Analyzer** | Deterministic diff of OpenAPI contracts; emits evidence-cited findings (`api-doctor-diff/v1`). | Deterministic |
| **Impact Mapper** | Correlates findings to declared consumers, identifies affected endpoints, builds dependency graph. | Deterministic |
| **Migration Strategist** | Generates ordered migration steps with code snippets/warnings. Uses Gemma when configured, else deterministic fallback. | AI-bounded / Fallback |
| **Test Engineer** | Creates bounded regression checks tied to findings (max 24). | Deterministic |
| **Verification & Risk Agent** | Runs sandbox checks, computes residual risk, applies simulated compatibility shim on copy if requested. | Deterministic (sandbox execution) |

## Agent Skills Open Standard

- **Skill path:** `skills/api-migration/SKILL.md`
- **Spec:** [Agent Skills specification](https://agentskills.io/)
- **Frontmatter:** Includes `name`, `description`, `license`, `compatibility`, `allowed-tools`, `metadata` (author/version/category). Workflow, inputs/outputs, and safety rules are documented.

## Model Harness

This project includes a **custom, bounded model harness** (`backend/app/llm/`):

| Component | Purpose |
|---|---|
| `llm/base.py` | Common types, tracing hooks, error classes |
| `llm/prompts.py` | Versioned prompts (`migration-v1.3.0`), schema constraints |
| `llm/gemma.py` | Google GenAI adapter for Gemma with timeout, bounded retries, response validation, attempt tracking |
| `llm/fallback.py` | Deterministic migration plan generator (labelled, complete) |

**Harness features:** prompt versioning, structured I/O expectations, context handling (findings + specs), tool restrictions (no tool use in migration calls), timeouts (`GEMMA_TIMEOUT_SECONDS`), bounded retries (`GEMMA_MAX_RETRIES`), error handling, execution traces with provider/model/status, and evaluation via backend tests.

## Google Gemma 4 Integration

- **Model:** `gemma-4-26b-a4b-it` (default, configurable via `GEMMA_MODEL`)
- **Provider:** Google AI Studio via `google-genai==2.33.0`
- **Inference method:** Hosted API (chat/completions style via `google-genai`). Not downloaded/served locally.
- **Model card:** [Google Gemma](https://ai.google.dev/gemma)
- **License:** [Gemma Terms of Use](https://ai.google.dev/gemma/terms) (separate from project MIT license)
- **Behavior:** 
  - If `GEMINI_API_KEY` or `GOOGLE_API_KEY` is set and valid, Migration Strategist calls Gemma with evidence-cited findings and returns a validated migration plan.
  - If not configured or on failure/timeout, it uses the deterministic fallback, records `status: fallback` in traces, and clearly labels the plan source as `fallback`.
- **AI usage:** Recommendations are generated from real analysis inputs (findings, specs, consumers), not hardcoded demo strings.

## Prerequisites

- **Node.js** 24.19.0+ / **npm** 11.17.0+
- **Python** 3.12 (backend `.python-version`)
- **Git** (optional for local dev)

## Local Setup

### Backend

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
# source .venv/bin/activate

pip install -r requirements.txt
```

### Frontend

```bash
cd frontend
npm install
```

## Environment Variables

Copy `.env.example` to `.env` in the repo root or set variables as needed. **Never commit `.env` or secrets.**

| Variable | Required | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` / `GOOGLE_API_KEY` | No | — | Enables Gemma 4 calls. Without it, fallback mode is used. |
| `GEMMA_MODEL` | No | `gemma-4-26b-a4b-it` | Gemma model identifier |
| `GEMMA_TIMEOUT_SECONDS` | No | `25` | Model call timeout |
| `GEMMA_MAX_RETRIES` | No | `2` | Bounded retries |
| `MAX_BODY_BYTES` | No | `2097152` | Max request body (2MB) |
| `MAX_FINDINGS` | No | `250` | Max findings limit |
| `MAX_TESTS` | No | `24` | Max generated tests |
| `SANDBOX_BUDGET_MS` | No | `5000` | Sandbox execution budget |
| `CORS_ORIGINS` | No | `http://localhost:5173,http://127.0.0.1:5173` | Allowed origins |
| `VITE_API_BASE_URL` | No | `http://127.0.0.1:8000` | Frontend API base URL |

## Running Locally

### Backend (development)

```bash
# From repo root, with venv activated
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Or from repo root:
```bash
backend\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**Health:** `GET http://127.0.0.1:8000/health` or `GET http://127.0.0.1:8000/api/health`

### Frontend (development)

```bash
cd frontend
npm run dev
```

Open `http://127.0.0.1:5173/`

## Build & Test

### Backend tests

```bash
# From repo root
backend\.venv\Scripts\python.exe -m pytest tests -q
```

**Current status:** 38 passed, 1 warning

### Frontend build/typecheck

```bash
cd frontend
npm run typecheck
npm run build
```

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Service info |
| GET | `/health` | Health check (model/provider/fallback status) |
| GET | `/api/health` | API health check |
| GET | `/api/agents` | List the 5 agents |
| GET | `/api/samples` | Demo fixtures (old/new specs, consumers) |
| POST | `/api/analyze` | Analyze contract pair, return full diagnosis |
| POST | `/api/verify` | Run sandbox verification; optional `apply_compatibility_patch` |

## Demo

The app includes a built-in **"Run sample diagnosis"** using Acme Payments v1→v2 (3 consumers). It demonstrates the full flow: 9 breaking/7 non-breaking changes, impact mapping, migration plan, 7 regression tests, and sandbox verification.

## Deployment

### Backend (Render / Vercel Python)

The backend includes `backend/vercel.json` and `backend/.python-version` for Vercel Python runtime. It can also be deployed to Render/Fly/Railway. Ensure:

- Build command: `pip install -r requirements.txt` (from backend dir)
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Set environment variables (never commit secrets)
- Configure CORS for your frontend domain
- Health check: `/health`

### Frontend (Vercel)

From `frontend/` directory:
- Framework: Vite
- Build command: `npm run build`
- Output directory: `dist`
- Set `VITE_API_BASE_URL` to your deployed backend URL
- Set `VITE_REPOSITORY_URL` if desired

## Security & Compliance

- No secrets committed; `.gitignore` excludes `.env` and credentials
- `.env.example` provided with safe placeholders
- API keys never exposed to frontend bundles
- Compatibility patches applied to copies only
- Sandbox never calls external services
- AI calls bounded by timeout/retries
- Input validation and body size limits enforced

## Third-Party Licenses

- **Project code:** MIT License (see [LICENSE](LICENSE))
- **Google Gemma:** [Gemma Terms of Use](https://ai.google.dev/gemma/terms) — separate license terms apply to model use
- **Dependencies:** See `backend/requirements.txt` and `frontend/package.json` for versions; refer to respective packages for their licenses

## Known Limitations

- Gemma requires API key from Google AI Studio; without it, only deterministic fallback is used
- Sandbox is a contract simulator, not a live service integration test
- Compatibility shim is simulated and cannot auto-fix semantic/auth/server config changes
- Consumer mapping relies on declared consumers (not runtime traffic)
- Some deployment platforms may have cold-start behavior

## Contributing

This is a hackathon project. See the repository for issues and guidelines.

## Links

- **GitHub:** `https://github.com/Amna503/api-doctor-ai` (to be created/pushed)
- **Live Frontend:** https://api-doctor-ai-frontend.vercel.app/ 
- **Live Backend Health:** (to be deployed)
