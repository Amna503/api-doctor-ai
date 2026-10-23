import { ChevronDown, TerminalSquare, X } from "lucide-react";
import { useEffect, useState } from "react";
import { formatDateTime, formatDuration } from "../lib/format";
import type { AnalysisResult, ExecutionTrace, VerificationResult } from "../types";
import { CopyButton, StatusBadge, cn } from "./ui";

function traceTone(status: ExecutionTrace["status"]) {
  if (status === "success") return "ok" as const;
  if (status === "fallback") return "warn" as const;
  if (status === "error") return "bad" as const;
  return "neutral" as const;
}

function TraceItem({ trace, index }: { trace: ExecutionTrace; index: number }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative pl-6">
      <span
        className={cn(
          "absolute left-0 top-3 h-2 w-2 -translate-x-[3.5px] rounded-full",
          trace.status === "success" && "bg-acid",
          trace.status === "fallback" && "bg-medium",
          trace.status === "error" && "bg-critical",
          trace.status === "skipped" && "bg-faint",
        )}
      />
      {index > 0 ? <span className="absolute bottom-0 left-0 top-0 border-l border-dashed border-white/12" /> : null}
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="w-full border-b border-white/[0.06] py-2.5 pr-2 text-left transition-colors hover:bg-white/[0.02]"
        aria-expanded={open}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="text-[11px] font-medium text-white/90">{trace.agent}</p>
            <p className="mt-0.5 text-[10px] leading-relaxed text-faint">{trace.action}</p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <StatusBadge tone={traceTone(trace.status)}>{trace.status}</StatusBadge>
            <ChevronDown
              size={12}
              className={cn("text-faint transition-transform", open && "rotate-180")}
            />
          </div>
        </div>
        <div className="mono mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-[8px] uppercase tracking-[0.1em] text-faint">
          <span>{formatDuration(trace.duration_ms)}</span>
          <span>attempt {trace.attempt}</span>
          {trace.provider ? <span>{trace.provider}</span> : null}
          {trace.evidence_count !== null ? <span>{trace.evidence_count} evidence</span> : null}
        </div>
      </button>
      {open ? (
        <div className="space-y-2 border-b border-white/[0.06] py-2.5 pl-1 pr-2">
          {trace.model ? (
            <div className="mono flex justify-between gap-3 text-[9px]">
              <span className="text-faint">model</span>
              <span className="text-white/70">{trace.model}</span>
            </div>
          ) : null}
          {trace.prompt_version ? (
            <div className="mono flex justify-between gap-3 text-[9px]">
              <span className="text-faint">prompt</span>
              <span className="text-white/70">{trace.prompt_version}</span>
            </div>
          ) : null}
          <div className="mono flex justify-between gap-3 text-[9px]">
            <span className="text-faint">started</span>
            <span className="text-white/70">{formatDateTime(trace.started_at)}</span>
          </div>
          {trace.detail ? (
            <p className="text-[10px] leading-relaxed text-muted">{trace.detail}</p>
          ) : null}
          {trace.error ? (
            <p className="border border-critical/20 bg-critical/[0.05] p-2 text-[10px] leading-relaxed text-critical/85">
              {trace.error}
            </p>
          ) : null}
          <div className="flex justify-end">
            <CopyButton text={JSON.stringify(trace, null, 2)} label="Copy trace" />
          </div>
        </div>
      ) : null}
    </div>
  );
}

function TraceGroup({
  title,
  subtitle,
  traces,
}: {
  title: string;
  subtitle: string;
  traces: ExecutionTrace[];
}) {
  const total = traces.reduce((sum, trace) => sum + trace.duration_ms, 0);
  return (
    <div className="mb-5">
      <div className="mb-1 flex items-center justify-between gap-2">
        <p className="mono text-[9px] uppercase tracking-[0.14em] text-acid">{title}</p>
        <p className="mono text-[8px] uppercase tracking-[0.1em] text-faint">
          {traces.length} calls · {formatDuration(total)}
        </p>
      </div>
      <p className="mono mb-2 text-[8px] text-faint">{subtitle}</p>
      {traces.length ? (
        traces.map((trace, index) => (
          <TraceItem key={`${trace.agent}-${trace.action}-${index}`} trace={trace} index={index} />
        ))
      ) : (
        <p className="border border-dashed border-white/10 py-4 text-center text-[10px] text-faint">
          No traces recorded.
        </p>
      )}
    </div>
  );
}

export function TraceDrawer({
  open,
  onClose,
  analysis,
  verification,
}: {
  open: boolean;
  onClose: () => void;
  analysis: AnalysisResult | null;
  verification: VerificationResult | null;
}) {
  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKey);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", handleKey);
    };
  }, [open, onClose]);

  if (!open) return null;

  const allTraces = [...(analysis?.traces ?? []), ...(verification?.traces ?? [])];
  const success = allTraces.filter((trace) => trace.status === "success").length;
  const fallback = allTraces.filter((trace) => trace.status === "fallback").length;
  const errors = allTraces.filter((trace) => trace.status === "error").length;

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-label="Agent execution traces">
      <button
        type="button"
        onClick={onClose}
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        aria-label="Close traces"
      />
      <div className="relative flex h-full w-full max-w-xl flex-col border-l border-white/12 bg-[#080c0f] shadow-2xl">
        <div className="flex items-start justify-between gap-3 border-b border-white/[0.08] px-4 py-3.5">
          <div>
            <div className="flex items-center gap-2">
              <TerminalSquare size={15} className="text-acid" />
              <h2 className="text-sm font-semibold text-white">Agent execution traces</h2>
            </div>
            <p className="mono mt-1 text-[9px] uppercase tracking-[0.1em] text-faint">
              {analysis?.analysis_id ?? "no analysis"} · {allTraces.length} recorded calls
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center border border-white/10 text-muted transition-colors hover:border-white/25 hover:text-white"
            aria-label="Close traces panel"
            autoFocus
          >
            <X size={15} />
          </button>
        </div>

        <div className="grid grid-cols-4 divide-x divide-white/[0.07] border-b border-white/[0.08]">
          {[
            ["calls", allTraces.length],
            ["success", success],
            ["fallback", fallback],
            ["errors", errors],
          ].map(([label, value]) => (
            <div key={String(label)} className="px-3 py-2.5 text-center">
              <p className="mono text-sm font-semibold text-white">{value}</p>
              <p className="mono text-[8px] uppercase tracking-[0.12em] text-faint">{label}</p>
            </div>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-4">
          {analysis ? (
            <TraceGroup
              title="Diagnosis run"
              subtitle={`${formatDateTime(analysis.generated_at)} · ${analysis.deterministic_engine}`}
              traces={analysis.traces}
            />
          ) : null}
          {verification ? (
            <TraceGroup
              title="Verification run"
              subtitle={`${verification.run_id} · ${formatDateTime(verification.executed_at)}`}
              traces={verification.traces}
            />
          ) : null}
          {!analysis ? (
            <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
              <TerminalSquare size={22} className="text-faint" />
              <p className="text-sm text-faint">Run a diagnosis to inspect agent traces.</p>
            </div>
          ) : null}
        </div>

        <div className="border-t border-white/[0.08] px-4 py-3">
          <p className="text-[10px] leading-relaxed text-faint">
            Traces are recorded per agent call, including retries, model metadata, and fallback
            reasons. Verification traces come from real sandbox execution.
          </p>
        </div>
      </div>
    </div>
  );
}
