import {
  Bot,
  ChevronDown,
  FlaskConical,
  GitCompareArrows,
  Network,
  Search,
  ShieldCheck,
  TerminalSquare,
} from "lucide-react";
import { useMemo, useState } from "react";
import { formatDateTime, formatDuration, titleCase } from "../lib/format";
import type { AnalysisResult, ExecutionTrace, Finding, Severity } from "../types";
import {
  CodeBlock,
  CopyButton,
  MethodTag,
  SectionHeading,
  SeverityBadge,
  StatusBadge,
  cn,
} from "./ui";

const severityOrder: Severity[] = ["critical", "high", "medium", "low", "info"];

const agentIcons: Record<string, typeof Bot> = {
  "Contract Analyzer": GitCompareArrows,
  "Impact Mapper": Network,
  "Migration Strategist": Bot,
  "Test Engineer": FlaskConical,
  "Verification & Risk Agent": ShieldCheck,
};

function traceTone(status: ExecutionTrace["status"]) {
  if (status === "success") return "ok" as const;
  if (status === "fallback") return "warn" as const;
  if (status === "error") return "bad" as const;
  return "neutral" as const;
}

function FindingRow({ finding }: { finding: Finding }) {
  const [open, setOpen] = useState(false);
  const oldValue = finding.old_value === null ? null : JSON.stringify(finding.old_value, null, 2);
  const newValue = finding.new_value === null ? null : JSON.stringify(finding.new_value, null, 2);

  return (
    <div
      className={cn(
        "group border bg-white/[0.012] transition-colors",
        open ? "border-white/20 bg-white/[0.025]" : "border-white/[0.065] hover:border-white/15",
      )}
    >
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-start gap-3 px-3 py-3 text-left"
        aria-expanded={open}
      >
        <span
          className={cn(
            "mt-0.5 h-8 w-0.5 shrink-0",
            finding.severity === "critical" && "bg-critical",
            finding.severity === "high" && "bg-high",
            finding.severity === "medium" && "bg-medium",
            finding.severity === "low" && "bg-low",
            finding.severity === "info" && "bg-info/70",
          )}
        />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="mono text-[9px] uppercase tracking-[0.1em] text-faint">{finding.id}</span>
            <span className="mono text-[9px] text-faint/70">/</span>
            <span className="mono text-[9px] text-faint">{finding.rule}</span>
            {finding.breaking ? (
              <StatusBadge tone="bad">breaking</StatusBadge>
            ) : (
              <StatusBadge tone="neutral">additive</StatusBadge>
            )}
          </div>
          <p className="mt-1 text-[13px] font-medium leading-snug text-white/90">{finding.title}</p>
          <div className="mt-1.5 flex flex-wrap items-center gap-2">
            {finding.method ? <MethodTag method={finding.method} /> : null}
            <span className="mono truncate text-[10px] text-muted">
              {finding.path ?? finding.location}
            </span>
            {finding.parameter ? (
              <span className="mono text-[9px] text-faint">param: {finding.parameter}</span>
            ) : null}
          </div>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-2">
          <SeverityBadge severity={finding.severity} />
          <span className="mono text-[9px] text-faint">
            {Math.round(finding.confidence * 100)}% conf
          </span>
          <ChevronDown
            size={14}
            className={cn("text-faint transition-transform", open && "rotate-180")}
          />
        </div>
      </button>

      {open ? (
        <div className="border-t border-white/[0.07] px-3 py-3">
          <p className="text-[12px] leading-relaxed text-muted">{finding.detail}</p>
          <p className="mono mt-2 text-[10px] leading-relaxed text-white/70">
            <span className="text-faint">EVIDENCE </span>
            {finding.evidence}
          </p>
          {finding.suggestion ? (
            <p className="mt-2 border-l border-acid/40 pl-3 text-[12px] leading-relaxed text-white/75">
              {finding.suggestion}
            </p>
          ) : null}
          <div className="mt-3 grid gap-2 md:grid-cols-2">
            {oldValue ? <CodeBlock code={oldValue} label="legacy value" tone="before" maxHeight="170px" /> : null}
            {newValue ? <CodeBlock code={newValue} label="target value" tone="after" maxHeight="170px" /> : null}
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className="mono text-[9px] uppercase tracking-[0.12em] text-faint">
              location: <span className="text-muted">{finding.location}</span>
            </span>
            <span className="mono text-[9px] uppercase tracking-[0.12em] text-faint">
              source: <span className="text-muted">{finding.source}</span>
            </span>
            <CopyButton text={JSON.stringify(finding, null, 2)} label="Copy finding" />
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function AnalysisView({
  result,
  onOpenTraces,
}: {
  result: AnalysisResult;
  onOpenTraces: () => void;
}) {
  const [severityFilter, setSeverityFilter] = useState<Severity | "all">("all");
  const [breakingOnly, setBreakingOnly] = useState(false);
  const [query, setQuery] = useState("");
  const [showAll, setShowAll] = useState(false);

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return result.findings
      .filter((finding) => severityFilter === "all" || finding.severity === severityFilter)
      .filter((finding) => !breakingOnly || finding.breaking)
      .filter((finding) => {
        if (!normalized) return true;
        return [
          finding.id,
          finding.rule,
          finding.title,
          finding.detail,
          finding.path ?? "",
          finding.method ?? "",
          finding.location,
          finding.evidence,
        ]
          .join(" ")
          .toLowerCase()
          .includes(normalized);
      })
      .sort((a, b) => {
        if (a.breaking !== b.breaking) return a.breaking ? -1 : 1;
        return severityOrder.indexOf(a.severity) - severityOrder.indexOf(b.severity);
      });
  }, [result.findings, severityFilter, breakingOnly, query]);

  const visible = showAll ? filtered : filtered.slice(0, 8);
  const totalTraceMs = result.traces.reduce((sum, trace) => sum + trace.duration_ms, 0);
  const source = result.migration.source;

  return (
    <section id="diagnosis" className="border-y border-white/[0.06] bg-white/[0.012]">
      <div className="mx-auto w-full max-w-[1280px] scroll-mt-24 px-4 py-14 sm:px-6 lg:px-8 lg:py-20">
        <SectionHeading
          number="02"
          eyebrow="Diagnosis"
          title="The contract, dissected."
          description="Deterministic rules produce the findings. Every claim is tied to a path, a fragment, and an evidence string."
          action={
            <button
              type="button"
              onClick={onOpenTraces}
              className="mono inline-flex items-center gap-2 border border-white/12 bg-white/[0.025] px-3 py-2 text-[10px] uppercase tracking-[0.12em] text-muted transition-colors hover:border-acid/35 hover:text-acid"
            >
              <TerminalSquare size={13} />
              {result.traces.length} agent traces
            </button>
          }
        />

        <div className="panel overflow-hidden">
          <div className="flex flex-col justify-between gap-3 border-b border-white/[0.07] px-4 py-3 sm:flex-row sm:items-center">
            <div className="flex flex-wrap items-center gap-2">
              <span className="mono text-[10px] uppercase tracking-[0.14em] text-white">
                {result.analysis_id}
              </span>
              <StatusBadge tone="ok">deterministic findings</StatusBadge>
              <StatusBadge tone={source === "gemma" ? "ok" : "warn"}>
                migration: {source}
              </StatusBadge>
            </div>
            <div className="flex items-center gap-3">
              <span className="mono text-[9px] text-faint">{formatDateTime(result.generated_at)}</span>
              <span className="mono text-[9px] text-faint">
                agents {formatDuration(totalTraceMs)}
              </span>
            </div>
          </div>

          <div className="grid divide-y divide-white/[0.07] sm:grid-cols-2 sm:divide-x sm:divide-y-0 lg:grid-cols-4">
            {[
              {
                label: "Breaking signals",
                value: result.summary.breaking_changes,
                note: `of ${result.summary.total_changes} contract changes`,
                tone: "text-critical",
              },
              {
                label: "Affected operations",
                value: result.summary.operations_affected,
                note: `${result.old_spec.endpoint_count} legacy / ${result.new_spec.endpoint_count} target`,
                tone: "text-high",
              },
              {
                label: "Consumers mapped",
                value: result.impact.consumers.length,
                note: `${result.impact.affected_endpoints.length} endpoints touched`,
                tone: "text-cyan",
              },
              {
                label: "Regression checks",
                value: result.tests.tests.length,
                note: "generated, not yet executed",
                tone: "text-acid",
              },
            ].map((stat) => (
              <div key={stat.label} className="px-4 py-4">
                <p className="mono text-[9px] uppercase tracking-[0.14em] text-faint">{stat.label}</p>
                <p className={cn("mt-1 text-3xl font-semibold tracking-[-0.04em]", stat.tone)}>
                  {stat.value}
                </p>
                <p className="mt-1 text-[10px] text-muted">{stat.note}</p>
              </div>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-white/[0.07] px-4 py-2.5">
            <span className="mono text-[9px] uppercase tracking-[0.1em] text-faint">
              legacy <span className="text-cyan">v{result.old_spec.version}</span> · {result.old_spec.title}
            </span>
            <span className="mono text-[9px] text-faint">→</span>
            <span className="mono text-[9px] uppercase tracking-[0.1em] text-faint">
              target <span className="text-acid">v{result.new_spec.version}</span> · {result.new_spec.title}
            </span>
            <span className="mono ml-auto text-[9px] text-faint">{result.deterministic_engine}</span>
          </div>
        </div>

        <div className="mt-5 grid gap-2 sm:grid-cols-2 xl:grid-cols-5">
          {result.traces.map((trace, index) => {
            const Icon = agentIcons[trace.agent] ?? Bot;
            return (
              <div
                key={`${trace.agent}-${index}`}
                className="fade-up relative border border-white/[0.07] bg-panel/80 p-3"
                style={{ animationDelay: `${index * 55}ms` }}
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="flex h-8 w-8 items-center justify-center border border-white/10 bg-white/[0.025] text-muted">
                    <Icon size={14} />
                  </span>
                  <StatusBadge tone={traceTone(trace.status)}>{trace.status}</StatusBadge>
                </div>
                <p className="mt-3 text-[12px] font-semibold text-white/90">{trace.agent}</p>
                <p className="mt-0.5 line-clamp-2 text-[10px] leading-relaxed text-faint">
                  {trace.action}
                </p>
                <div className="mono mt-2 flex items-center justify-between text-[9px] text-faint">
                  <span>{formatDuration(trace.duration_ms)}</span>
                  <span>try {trace.attempt}</span>
                </div>
              </div>
            );
          })}
        </div>

        <div className="mt-10">
          <div className="mb-3 flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
            <div className="flex flex-wrap items-center gap-1.5">
              <button
                type="button"
                onClick={() => setSeverityFilter("all")}
                className={cn(
                  "mono border px-2.5 py-1.5 text-[10px] uppercase tracking-[0.1em] transition-colors",
                  severityFilter === "all"
                    ? "border-acid/40 bg-acid/10 text-acid"
                    : "border-white/10 text-muted hover:border-white/25 hover:text-white",
                )}
              >
                all · {result.findings.length}
              </button>
              {severityOrder.map((severity) => {
                const count = result.findings.filter((finding) => finding.severity === severity).length;
                return (
                  <button
                    key={severity}
                    type="button"
                    onClick={() => setSeverityFilter(severity)}
                    disabled={count === 0}
                    className={cn(
                      "mono border px-2.5 py-1.5 text-[10px] uppercase tracking-[0.1em] transition-colors disabled:cursor-not-allowed disabled:opacity-35",
                      severityFilter === severity
                        ? "border-white/30 bg-white/10 text-white"
                        : "border-white/10 text-muted hover:border-white/25 hover:text-white",
                    )}
                  >
                    {severity} · {count}
                  </button>
                );
              })}
              <button
                type="button"
                onClick={() => setBreakingOnly((value) => !value)}
                className={cn(
                  "mono border px-2.5 py-1.5 text-[10px] uppercase tracking-[0.1em] transition-colors",
                  breakingOnly
                    ? "border-critical/40 bg-critical/10 text-critical"
                    : "border-white/10 text-muted hover:border-white/25 hover:text-white",
                )}
              >
                breaking only
              </button>
            </div>
            <div className="relative">
              <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-faint" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Filter findings, paths, rules…"
                aria-label="Filter findings"
                className="mono w-full border border-white/10 bg-black/25 py-1.5 pl-7 pr-2.5 text-[10px] text-white outline-none placeholder:text-faint focus:border-acid/35 xl:w-[260px]"
              />
            </div>
          </div>

          <div className="space-y-2">
            {visible.map((finding) => (
              <FindingRow key={finding.id} finding={finding} />
            ))}
            {visible.length === 0 ? (
              <div className="border border-white/[0.07] bg-white/[0.012] px-4 py-10 text-center">
                <p className="text-sm text-muted">No findings match this filter.</p>
                <button
                  type="button"
                  onClick={() => {
                    setSeverityFilter("all");
                    setBreakingOnly(false);
                    setQuery("");
                  }}
                  className="mono mt-2 text-[10px] uppercase tracking-[0.1em] text-acid hover:underline"
                >
                  clear filters
                </button>
              </div>
            ) : null}
          </div>

          {filtered.length > 8 ? (
            <button
              type="button"
              onClick={() => setShowAll((value) => !value)}
              className="mono mt-3 flex w-full items-center justify-center gap-2 border border-white/10 bg-white/[0.02] py-2.5 text-[10px] uppercase tracking-[0.12em] text-muted transition-colors hover:border-white/25 hover:text-white"
            >
              {showAll ? "collapse findings" : `show all ${filtered.length} findings`}
              <ChevronDown size={12} className={cn(showAll && "rotate-180")} />
            </button>
          ) : null}
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-2">
          {severityOrder.map((severity) => (
            <span key={severity} className="flex items-center gap-1.5">
              <SeverityBadge severity={severity} />
              <span className="mono text-[9px] text-faint">
                {titleCase(severity)}: {result.summary.by_severity[severity] ?? 0}
              </span>
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
