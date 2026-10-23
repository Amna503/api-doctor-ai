import {
  AlertTriangle,
  CircleCheck,
  CircleSlash,
  CircleX,
  Clock3,
  FlaskConical,
  Play,
  RefreshCw,
  ShieldCheck,
  TerminalSquare,
  Wrench,
} from "lucide-react";
import { useMemo, useState } from "react";
import { formatDateTime, formatDuration, titleCase } from "../lib/format";
import type { AnalysisResult, TestResult, VerificationResult } from "../types";
import {
  Button,
  CodeBlock,
  CopyButton,
  ScoreRing,
  SectionHeading,
  StatusBadge,
  cn,
} from "./ui";

function testStatusIcon(status: TestResult["status"]) {
  if (status === "passed") return <CircleCheck size={13} className="text-acid" />;
  if (status === "failed") return <CircleX size={13} className="text-critical" />;
  return <CircleSlash size={13} className="text-faint" />;
}

const typeLabels: Record<string, string> = {
  endpoint_available: "reachability",
  legacy_request: "legacy request",
  response_contract: "response contract",
};

export function VerificationSection({
  analysis,
  verification,
  verifyMode,
  error,
  onVerify,
  onOpenTraces,
}: {
  analysis: AnalysisResult;
  verification: VerificationResult | null;
  verifyMode: "standard" | "patch" | null;
  error: string | null;
  onVerify: (applyPatch: boolean) => void;
  onOpenTraces: () => void;
}) {
  const [filter, setFilter] = useState<"all" | "failed" | "passed">("all");
  const [openTest, setOpenTest] = useState<string | null>(null);
  const risk = verification?.risk ?? analysis.risk;
  const verified = Boolean(verification);
  const patch = verification?.compatibility_patch ?? null;
  const resultMap = useMemo(
    () => new Map((verification?.results ?? []).map((result) => [result.test_id, result])),
    [verification],
  );

  const tests = analysis.tests.tests.filter((test) => {
    if (filter === "all") return true;
    const result = resultMap.get(test.id);
    if (filter === "failed") return result?.status === "failed";
    if (filter === "passed") return result?.status === "passed";
    return true;
  });

  const statusLabel =
    risk.status === "verified_compatible"
      ? "verified compatible"
      : risk.status === "unresolved_risks"
        ? "unresolved risks"
        : "not executed";
  const statusTone =
    risk.status === "verified_compatible" ? "ok" : risk.status === "unresolved_risks" ? "bad" : "warn";

  return (
    <section id="verify" className="mx-auto w-full max-w-[1280px] scroll-mt-24 px-4 py-14 sm:px-6 lg:px-8 lg:py-20">
      <SectionHeading
        number="05"
        eyebrow="Sandbox verification"
        title="Prove it. Don't claim it."
        description="Generated regression checks execute against the actual target contract with JSON-Schema validation. Results, residual risk, and failures are reported exactly as they run."
        action={
          <div className="flex items-center gap-2">
            <StatusBadge tone="neutral">{analysis.tests.tests.length} checks</StatusBadge>
            <StatusBadge tone={statusTone}>{statusLabel}</StatusBadge>
          </div>
        }
      />

      <div className="panel overflow-hidden">
        <div className="flex flex-col justify-between gap-2 border-b border-white/[0.07] px-4 py-3 sm:flex-row sm:items-center">
          <div className="flex flex-wrap items-center gap-2">
            <FlaskConical size={14} className="text-acid" />
            <span className="mono text-[10px] uppercase tracking-[0.14em] text-white">
              Verification lab
            </span>
            <StatusBadge tone="neutral">{analysis.tests.sandbox}</StatusBadge>
          </div>
          <div className="flex items-center gap-3">
            <span className="mono text-[9px] text-faint">
              {verified && verification ? formatDateTime(verification.executed_at) : "not yet executed"}
            </span>
            <button
              type="button"
              onClick={onOpenTraces}
              className="mono inline-flex items-center gap-1.5 border border-white/10 px-2 py-1 text-[9px] uppercase tracking-[0.1em] text-muted transition-colors hover:border-acid/35 hover:text-acid"
            >
              <TerminalSquare size={11} /> traces
            </button>
          </div>
        </div>

        {error ? (
          <div className="flex items-start gap-2 border-b border-critical/25 bg-critical/[0.06] px-4 py-2.5">
            <AlertTriangle size={13} className="mt-0.5 shrink-0 text-critical" />
            <p className="text-[11px] leading-relaxed text-critical/90">{error}</p>
          </div>
        ) : null}

        <div className="grid gap-4 p-4 lg:grid-cols-[330px_1fr] lg:p-5">
          <div className="border border-white/[0.075] bg-black/20 p-4">
            <div className="flex items-start justify-between gap-2">
              <p className="mono text-[9px] uppercase tracking-[0.14em] text-faint">Risk assessment</p>
              <StatusBadge tone={statusTone}>{risk.status.replaceAll("_", " ")}</StatusBadge>
            </div>

            <div className="mt-3 flex items-center gap-4">
              <ScoreRing score={risk.score} level={risk.level} verified={risk.verified} size={122} />
              <div className="min-w-0">
                <p className="text-[13px] font-semibold text-white">{titleCase(risk.level)}</p>
                <p className="mono mt-1 text-[9px] uppercase tracking-[0.12em] text-faint">
                  {risk.verified ? "measured by sandbox" : "deterministic pre-check"}
                </p>
                {verification ? (
                  <div className="mt-2 flex items-center gap-1.5">
                    <span className="mono text-[9px] text-faint line-through">{analysis.risk.score}</span>
                    <span className="mono text-[9px] text-faint">→</span>
                    <span className="mono text-[10px] font-semibold text-white">{risk.score}</span>
                  </div>
                ) : null}
                <p className="mono mt-1 text-[9px] text-faint">
                  {Math.round(risk.evidence_coverage * 100)}% evidence coverage
                </p>
              </div>
            </div>

            <p className="mt-3 text-[11px] leading-relaxed text-muted">{risk.summary}</p>

            <div className="mt-3 grid grid-cols-3 divide-x divide-white/[0.08] border-y border-white/[0.07] py-2.5">
              {[
                ["passed", verification?.passed ?? 0, "text-acid"],
                ["failed", verification?.failed ?? 0, "text-critical"],
                ["skipped", verification?.skipped ?? 0, "text-faint"],
              ].map(([label, value, tone]) => (
                <div key={String(label)} className="px-2 text-center">
                  <p className={cn("text-lg font-semibold", String(tone))}>{value}</p>
                  <p className="mono text-[8px] uppercase tracking-[0.12em] text-faint">{label}</p>
                </div>
              ))}
            </div>

            <div className="mt-3 space-y-2">
              {!verified ? (
                <Button
                  onClick={() => onVerify(false)}
                  loading={verifyMode === "standard"}
                  disabled={verifyMode !== null}
                  className="w-full"
                >
                  <Play size={14} /> Run sandbox verification
                </Button>
              ) : (
                <>
                  <Button
                    onClick={() => onVerify(true)}
                    loading={verifyMode === "patch"}
                    disabled={verifyMode !== null}
                    className="w-full"
                  >
                    <Wrench size={14} /> {patch ? "Re-verify shim" : "Apply shim & re-verify"}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => onVerify(false)}
                    loading={verifyMode === "standard"}
                    disabled={verifyMode !== null}
                    className="w-full"
                  >
                    <RefreshCw size={13} /> Run without shim
                  </Button>
                </>
              )}
            </div>

            <p className="mt-2.5 flex items-start gap-1.5 text-[10px] leading-relaxed text-faint">
              <ShieldCheck size={11} className="mt-0.5 shrink-0" />
              Isolated contract simulation. Your services are never called.
            </p>

            {risk.unresolved.length ? (
              <div className="mt-3 border-t border-white/[0.07] pt-2.5">
                <p className="mono text-[9px] uppercase tracking-[0.12em] text-critical">
                  Unresolved · {risk.unresolved.length}
                </p>
                <div className="mt-1.5 max-h-[128px] space-y-1 overflow-y-auto pr-1">
                  {risk.unresolved.map((item) => (
                    <p key={item} className="mono text-[9px] leading-relaxed text-faint">
                      {item}
                    </p>
                  ))}
                </div>
              </div>
            ) : null}
          </div>

          <div className="min-w-0">
            <div className="mb-2 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-1">
                {(["all", "failed", "passed"] as const).map((value) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setFilter(value)}
                    className={cn(
                      "mono border px-2 py-1 text-[9px] uppercase tracking-[0.1em] transition-colors",
                      filter === value
                        ? "border-white/25 bg-white/10 text-white"
                        : "border-white/10 text-faint hover:text-white",
                    )}
                  >
                    {value}
                  </button>
                ))}
              </div>
              <p className="mono text-[9px] uppercase tracking-[0.1em] text-faint">
                {verified && verification
                  ? `run ${verification.run_id} · ${formatDuration(verification.duration_ms)}`
                  : "awaiting execution"}
              </p>
            </div>

            <div className="space-y-1.5">
              {tests.map((test) => {
                const result = resultMap.get(test.id);
                const open = openTest === test.id;
                return (
                  <div
                    key={test.id}
                    className={cn(
                      "border bg-white/[0.012] transition-colors",
                      open ? "border-white/20 bg-white/[0.025]" : "border-white/[0.065]",
                    )}
                  >
                    <button
                      type="button"
                      onClick={() => setOpenTest(open ? null : test.id)}
                      className="flex w-full items-start gap-3 px-3 py-2.5 text-left"
                      aria-expanded={open}
                    >
                      <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center">
                        {result ? testStatusIcon(result.status) : <Clock3 size={12} className="text-faint" />}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[12px] font-medium text-white/90">{test.name}</p>
                        <div className="mt-1 flex flex-wrap items-center gap-2">
                          <span className="mono text-[8px] uppercase tracking-[0.1em] text-faint">
                            {typeLabels[test.type] ?? test.type}
                          </span>
                          <span className="mono text-[8px] text-faint">
                            {test.method} {test.path}
                          </span>
                          {result ? (
                            <span className="mono text-[8px] text-faint">
                              {formatDuration(result.duration_ms)}
                            </span>
                          ) : null}
                        </div>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        {result ? (
                          <StatusBadge
                            tone={
                              result.status === "passed"
                                ? "ok"
                                : result.status === "failed"
                                  ? "bad"
                                  : "neutral"
                            }
                          >
                            {result.status}
                          </StatusBadge>
                        ) : (
                          <StatusBadge tone="neutral">queued</StatusBadge>
                        )}
                      </div>
                    </button>
                    {open ? (
                      <div className="border-t border-white/[0.07] px-3 py-3">
                        <p className="text-[11px] leading-relaxed text-muted">{test.description}</p>
                        <div className="mt-2 grid gap-2 md:grid-cols-2">
                          <div className="border border-white/[0.07] bg-black/20 p-2.5">
                            <p className="mono text-[8px] uppercase tracking-[0.12em] text-faint">
                              expected
                            </p>
                            <p className="mt-1 text-[10px] leading-relaxed text-white/75">
                              {test.expected}
                            </p>
                          </div>
                          <div className="border border-white/[0.07] bg-black/20 p-2.5">
                            <p className="mono text-[8px] uppercase tracking-[0.12em] text-faint">
                              actual sandbox output
                            </p>
                            <p
                              className={cn(
                                "mt-1 text-[10px] leading-relaxed",
                                result?.status === "failed" ? "text-critical/85" : "text-white/75",
                              )}
                            >
                              {result ? result.actual : "Not executed yet. Run the sandbox to obtain a real result."}
                            </p>
                          </div>
                        </div>
                        {result?.evidence.length ? (
                          <ul className="mt-2 space-y-1">
                            {result.evidence.map((evidence) => (
                              <li key={evidence} className="mono text-[9px] leading-relaxed text-faint">
                                · {evidence}
                              </li>
                            ))}
                          </ul>
                        ) : null}
                        <div className="mt-2 flex flex-wrap items-center gap-1.5">
                          {test.finding_ids.map((id) => (
                            <span
                              key={id}
                              className="mono border border-white/10 bg-black/20 px-1.5 py-0.5 text-[8px] text-faint"
                            >
                              {id}
                            </span>
                          ))}
                          <span className="ml-auto">
                            <CopyButton text={test.code} label="Copy test" />
                          </span>
                        </div>
                        <div className="mt-2">
                          <CodeBlock code={test.code} label="generated check" maxHeight="220px" />
                        </div>
                      </div>
                    ) : null}
                  </div>
                );
              })}
              {tests.length === 0 ? (
                <div className="border border-white/[0.07] bg-white/[0.012] px-4 py-8 text-center">
                  <p className="text-[12px] text-muted">No checks match this filter.</p>
                </div>
              ) : null}
            </div>

            <div className="mt-3 border border-white/[0.07] bg-white/[0.015] px-3 py-2.5">
              <p className="mono text-[9px] leading-relaxed text-faint">
                {analysis.tests.note}
              </p>
              {verified && verification ? (
                <div className="mono mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-[9px] uppercase tracking-[0.1em] text-faint">
                  <span>sandbox: {verification.sandbox}</span>
                  <span>run: {verification.run_id}</span>
                  <span>total: {formatDuration(verification.duration_ms)}</span>
                </div>
              ) : null}
            </div>
          </div>
        </div>

        {patch ? (
          <div className="border-t border-white/[0.07] bg-black/15 p-4 lg:p-5">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-2">
                <Wrench size={14} className="text-cyan" />
                <span className="mono text-[10px] uppercase tracking-[0.14em] text-white">
                  Compatibility shim · simulated
                </span>
                <StatusBadge tone={patch.residual_breaking_changes === 0 ? "ok" : "warn"}>
                  {patch.residual_breaking_changes} residual
                </StatusBadge>
              </div>
              <span className="mono text-[9px] text-faint">
                original contract untouched
              </span>
            </div>
            <p className="mt-2 max-w-3xl text-[11px] leading-relaxed text-muted">{patch.description}</p>
            <div className="mt-3 grid gap-3 lg:grid-cols-3">
              <div className="border border-white/[0.07] bg-white/[0.012] p-3">
                <p className="mono text-[9px] uppercase tracking-[0.12em] text-acid">
                  Changes applied · {patch.changes.length}
                </p>
                <ul className="mt-2 space-y-1">
                  {patch.changes.map((change) => (
                    <li key={change} className="flex items-start gap-2 text-[10px] leading-relaxed text-muted">
                      <CircleCheck size={10} className="mt-0.5 shrink-0 text-acid/70" />
                      {change}
                    </li>
                  ))}
                </ul>
              </div>
              <div className="border border-white/[0.07] bg-white/[0.012] p-3">
                <p className="mono text-[9px] uppercase tracking-[0.12em] text-medium">
                  Still unpatchable · {patch.remaining_unpatchable.length}
                </p>
                <ul className="mt-2 space-y-1">
                  {patch.remaining_unpatchable.map((item) => (
                    <li key={item} className="flex items-start gap-2 text-[10px] leading-relaxed text-muted">
                      <AlertTriangle size={10} className="mt-0.5 shrink-0 text-medium/70" />
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
              <div className="border border-white/[0.07] bg-white/[0.012] p-3">
                <p className="mono text-[9px] uppercase tracking-[0.12em] text-critical">
                  Residual breaking findings · {patch.residual_findings.length}
                </p>
                <ul className="mt-2 space-y-1">
                  {patch.residual_findings.map((item) => (
                    <li key={item} className="mono text-[9px] leading-relaxed text-faint">
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}
