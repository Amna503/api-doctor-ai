---
name: api-migration
description: "Analyze OpenAPI breaking changes, map consumer impact, generate evidence-cited migration guidance with Gemma, produce bounded regression checks, and verify with a sandbox."
license: MIT
compatibility: "Requires access to OpenAPI JSON (v2/v3), optional declared consumers."
allowed-tools: Read Grep WebFetch
metadata:
  author: "API Doctor AI"
  version: "1.0.0"
  category: "api-contracts"
---

# API Migration Skill

## Purpose

This skill guides API Doctor AI through breaking-change analysis of OpenAPI specifications. It produces deterministic findings, maps blast radius to declared consumers, drafts evidence-cited migration plans (with bounded AI assistance), generates regression tests, and verifies fixes in a sandbox.

## When to use

Use this skill when comparing two OpenAPI documents (`old_spec` and `new_spec`) and you need to identify breaking changes, assess consumer impact, plan migration steps, create regression checks, and measure residual risk.

## Inputs

- `old_spec` (object, required): OpenAPI/Swagger JSON for the current contract
- `new_spec` (object, required): OpenAPI/Swagger JSON for the target contract  
- `consumers` (array, optional): Declared consumers `[{name, owner?, endpoints[]}]`
- `apply_compatibility_patch` (boolean, optional): Apply simulated compatibility shim during verification

## Outputs

- `analysis_id`: Deterministic analysis identifier
- `findings[]`: Evidence-cited breaking/non-breaking changes with severity, location, evidence
- `impact`: Affected endpoints, consumers, and dependency graph
- `migration`: Strategy and ordered steps (Gemma-assisted when configured, otherwise deterministic fallback)
- `tests[]`: Bounded regression checks with expected behavior
- `risk`: Pre/post verification risk assessment
- `verification`: Sandbox execution results with pass/fail and residual risk
- `traces[]`: Agent execution traces

## Workflow

1. **Contract analysis** - Deterministically diff old vs new specs (endpoints, parameters, schemas, security, servers). Every finding must cite evidence.
2. **Impact mapping** - Correlate findings to declared consumers/endpoints and build a topology graph.
3. **Migration strategy** - Generate evidence-cited migration steps. If `GEMINI_API_KEY` is configured, use Gemma (`gemma-4-26b-a4b-it` by default) with timeout/retries/schema validation; otherwise use deterministic fallback and label it clearly.
4. **Test engineering** - Create bounded regression checks (reachability, legacy request acceptance, response contract) tied to findings.
5. **Verification & risk** - Execute checks in an isolated sandbox against the target contract. Optionally apply a simulated compatibility shim (non-destructive copy) to measure residual risk. Report actual results only.

## Safety rules

- Never call production services or exfiltrate secrets
- Deterministic rules take precedence for findings; AI suggestions are advisory
- All model calls must be bounded by timeout and retry limits
- Fallback mode must be clearly indicated when AI is unavailable
- Verification results must reflect actual sandbox execution, never fabricated
- Compatibility patches are simulated on copies and never modify original contracts
- Evidence is required for breaking findings
- Respect body size limits and input validation

## References

- [Agent Skills specification](https://agentskills.io/)
- [OpenAPI Specification](https://spec.openapis.org/oas/latest.html)
- [Google Gemma model card](https://ai.google.dev/gemma)
