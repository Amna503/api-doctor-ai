from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel, ConfigDict, Field

from ..analysis.differ import SEVERITY_ORDER
from ..analysis.loader import LoadedSpec
from ..models import Finding, GeneratedTest, GeneratedTests
from .base import BaseAgent


class EngineerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    findings: list[Finding]
    max_tests: int = Field(default=24, ge=1, le=40)


def _success_code(codes: list[str]) -> str:
    for code in codes:
        if code.startswith("2"):
            return code
    return codes[0] if codes else "200"


def _finding_severity(items: list[Finding]) -> str:
    return sorted(items, key=lambda item: SEVERITY_ORDER.get(item.severity, 9))[0].severity


def _slug(value: str) -> str:
    out = "".join(char if char.isalnum() else "_" for char in value.lower())
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("_")[:60]


class TestEngineer(BaseAgent):
    name = "Test Engineer"
    responsibility = (
        "Generate bounded regression tests from deterministic findings: legacy endpoint reachability, "
        "legacy request conformance, and response-shape compatibility. Generated test code is shown to "
        "developers; execution uses the safe structured sandbox, never arbitrary code."
    )
    timeout_seconds = 5.0
    max_retries = 0

    def run(
        self, payload: EngineerInput, old: LoadedSpec, new: LoadedSpec
    ) -> GeneratedTests:
        grouped: dict[tuple[str, str], list[Finding]] = defaultdict(list)
        for finding in payload.findings:
            if finding.method and finding.path:
                grouped[(finding.method, finding.path)].append(finding)
        ordered = sorted(
            grouped.items(),
            key=lambda item: (
                SEVERITY_ORDER.get(_finding_severity(item[1]), 9),
                item[0][1],
                item[0][0],
            ),
        )
        tests: list[GeneratedTest] = []
        counter = 1
        for (method, path), items in ordered:
            old_op = old.operations.get(f"{method} {path}")
            new_op = new.operations.get(f"{method} {path}")
            if old_op is None:
                continue
            breaking = any(item.breaking for item in items)
            if not breaking:
                continue
            finding_ids = [item.id for item in items]
            request_ids = [
                item.id
                for item in items
                if not item.kind.startswith("response_")
                and item.kind not in {"security_changed", "servers_changed"}
            ]
            if new_op is None:
                if len(tests) >= payload.max_tests:
                    break
                tests.append(
                    GeneratedTest(
                        id=f"TST-{counter:03d}",
                        name=f"legacy endpoint reachable: {method} {path}",
                        description=(
                            "A legacy consumer still calls this route. The test fails when the route "
                            "is absent from the target contract."
                        ),
                        type="endpoint_available",
                        method=method,
                        path=path,
                        finding_ids=finding_ids,
                        check={"expect_available": True},
                        expected=f"{method} {path} remains reachable",
                        code=(
                            "def test_legacy_endpoint_available(api):\n"
                            f"    assert api.operation_exists(\"{method}\", \"{path}\"), "
                            "\"removed route breaks legacy callers\"\n"
                        ),
                    )
                )
                counter += 1
                continue

            if len(tests) < payload.max_tests:
                tests.append(
                    GeneratedTest(
                        id=f"TST-{counter:03d}",
                        name=f"legacy request accepted: {method} {path}",
                        description=(
                            "Builds a request from the old contract (parameters and body) and validates "
                            "it against the target operation using JSON Schema."
                        ),
                        type="legacy_request",
                        method=method,
                        path=path,
                        finding_ids=request_ids,
                        check={"comparison": "legacy-request-vs-new-contract"},
                        expected="Target contract accepts a legacy-shaped request",
                        code=(
                            "def test_legacy_request(api):\n"
                            f"    response = api.request(\"{method}\", \"{path}\", ...)\n"
                            "    assert response.status_code < 400, "
                            "\"legacy request rejected by the new contract\"\n"
                        ),
                    )
                )
                counter += 1

            response_findings = [item for item in items if item.kind.startswith("response_")]
            if new_op is not None and response_findings and len(tests) < payload.max_tests:
                old_codes = list(old_op.responses.keys())
                removed_codes = [
                    item.parameter for item in response_findings if item.kind == "response_code_removed"
                ]
                code = removed_codes[0] if removed_codes else _success_code(old_codes)
                tests.append(
                    GeneratedTest(
                        id=f"TST-{counter:03d}",
                        name=f"response contract preserved: {method} {path} {code}",
                        description=(
                            "Checks that the target response schema still exposes the fields and "
                            "compatible types that the old response contract promised."
                        ),
                        type="response_contract",
                        method=method,
                        path=path,
                        finding_ids=[item.id for item in response_findings],
                        check={"code": code, "comparison": "old-response-vs-new-response"},
                        expected=f"Response {code} remains structurally compatible",
                        code=(
                            "def test_response_contract(api):\n"
                            f"    body = api.response_fixture(\"{method}\", \"{path}\", {code})\n"
                            "    validate(body, new_response_schema)\n"
                        ),
                    )
                )
                counter += 1

        note = (
            "Generated pytest snippets are illustrative. The executed regression suite is a bounded, "
            "in-process sandbox of structured JSON Schema checks: no generated code is executed, no "
            "network calls are made, and no filesystem or shell access is available."
        )
        return GeneratedTests(
            note=note,
            tests=tests[: payload.max_tests],
        )
