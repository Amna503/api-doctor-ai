export type Severity = "critical" | "high" | "medium" | "low" | "info";
export type RiskLevel = Severity | "clean";

export interface Consumer {
  name: string;
  owner?: string | null;
  endpoints: string[];
}

export interface SpecMeta {
  title: string;
  version: string;
  openapi: string;
  endpoint_count: number;
  operations: string[];
  servers: string[];
}

export interface Finding {
  id: string;
  rule: string;
  kind: string;
  severity: Severity;
  breaking: boolean;
  title: string;
  detail: string;
  method: string | null;
  path: string | null;
  location: string;
  evidence: string;
  old_value: unknown;
  new_value: unknown;
  confidence: number;
  source: "deterministic" | "gemma" | "fallback" | "sandbox";
  suggestion: string | null;
  schema_pointer: string | null;
  parameter: string | null;
  old_fragment: unknown;
  new_fragment: unknown;
}

export interface AnalysisSummary {
  analysis_id: string;
  breaking_changes: number;
  non_breaking_changes: number;
  total_changes: number;
  by_severity: Record<string, number>;
  endpoints_added: number;
  endpoints_removed: number;
  operations_affected: number;
  old_endpoint_count: number;
  new_endpoint_count: number;
}

export interface AffectedEndpoint {
  method: string;
  path: string;
  severity: Severity;
  breaking: boolean;
  finding_ids: string[];
  consumers: string[];
  exists_in_new: boolean;
}

export interface AffectedConsumer {
  name: string;
  owner?: string | null;
  affected_endpoints: string[];
  finding_ids: string[];
  severity: Severity;
}

export interface GraphNode {
  id: string;
  label: string;
  kind: "consumer" | "endpoint";
  group: string;
  severity: Severity | null;
  meta: Record<string, unknown>;
}

export interface GraphEdge {
  source: string;
  target: string;
  label?: string | null;
}

export interface ImpactReport {
  affected_endpoints: AffectedEndpoint[];
  consumers: AffectedConsumer[];
  unclaimed_endpoints: string[];
  graph: { nodes: GraphNode[]; edges: GraphEdge[] };
}

export interface MigrationStep {
  id: string;
  title: string;
  detail: string;
  finding_ids: string[];
  confidence: number;
  code_before: string | null;
  code_after: string | null;
  notes: string | null;
}

export interface MigrationPlan {
  source: "gemma" | "fallback";
  model: string;
  prompt_version: string;
  summary: string;
  strategy: string;
  steps: MigrationStep[];
  warnings: string[];
  generated_at: string | null;
}

export interface GeneratedTest {
  id: string;
  name: string;
  description: string;
  type: "endpoint_available" | "legacy_request" | "response_contract";
  method: string;
  path: string;
  finding_ids: string[];
  check: Record<string, unknown>;
  expected: string;
  code: string;
}

export interface GeneratedTests {
  source: "deterministic";
  sandbox: string;
  note: string;
  tests: GeneratedTest[];
}

export interface ExecutionTrace {
  agent: string;
  action: string;
  status: "success" | "fallback" | "error" | "skipped";
  started_at: string;
  duration_ms: number;
  attempt: number;
  provider: string | null;
  model: string | null;
  prompt_version: string | null;
  detail: string | null;
  error: string | null;
  evidence_count: number | null;
}

export interface RiskAssessment {
  score: number;
  level: RiskLevel;
  verified: boolean;
  status: "unresolved_risks" | "verified_compatible" | "not_executed";
  unresolved_findings: number;
  resolved_findings: number;
  summary: string;
  unresolved: string[];
  evidence_coverage: number;
}

export interface AnalysisResult {
  analysis_id: string;
  generated_at: string;
  old_spec: SpecMeta;
  new_spec: SpecMeta;
  summary: AnalysisSummary;
  findings: Finding[];
  impact: ImpactReport;
  migration: MigrationPlan;
  tests: GeneratedTests;
  risk: RiskAssessment;
  traces: ExecutionTrace[];
  deterministic_engine: string;
  disclaimer: string;
}

export interface TestResult {
  test_id: string;
  name: string;
  type: string;
  method: string;
  path: string;
  finding_ids: string[];
  status: "passed" | "failed" | "skipped";
  expected: string;
  actual: string;
  evidence: string[];
  duration_ms: number;
}

export interface CompatibilityPatch {
  applied: boolean;
  description: string;
  changes: string[];
  remaining_unpatchable: string[];
  residual_breaking_changes: number;
  residual_findings: string[];
}

export interface VerificationResult {
  analysis_id: string;
  run_id: string;
  executed_at: string;
  duration_ms: number;
  sandbox: string;
  sandbox_notes: string;
  total: number;
  passed: number;
  failed: number;
  skipped: number;
  results: TestResult[];
  risk: RiskAssessment;
  compatibility_patch: CompatibilityPatch | null;
  traces: ExecutionTrace[];
}

export interface Health {
  status: "ok";
  service: string;
  version: string;
  environment: string;
  model_provider: string;
  model: string;
  model_configured: boolean;
  model_fallback: string;
  deterministic_engine: string;
  timestamp: string;
  uptime_seconds: number;
}

export interface AnalyzePayload {
  old_spec: Record<string, unknown>;
  new_spec: Record<string, unknown>;
  consumers: Consumer[];
}

export interface VerifyPayload extends AnalyzePayload {
  apply_compatibility_patch?: boolean;
}
