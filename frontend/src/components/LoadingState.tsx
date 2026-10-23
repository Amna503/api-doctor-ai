import { useEffect, useState } from "react";
import { Bot, FlaskConical, GitCompareArrows, Network, ShieldCheck } from "lucide-react";
import type { Health } from "../types";
import { StatusBadge } from "./ui";

const stages = [
  { icon: GitCompareArrows, label: "Parsing & diffing contracts", note: "deterministic rules · $ref resolution" },
  { icon: Network, label: "Mapping consumer exposure", note: "declared endpoints only" },
  { icon: Bot, label: "Drafting migration guidance", note: "Gemma when configured, fallback otherwise" },
  { icon: FlaskConical, label: "Generating regression checks", note: "bounded JSON-Schema assertions" },
  { icon: ShieldCheck, label: "Preparing sandbox risk model", note: "execution happens on your command" },
];

export function LoadingState({
  mode,
  startedAt,
  health,
}: {
  mode: "analyze" | "verify";
  startedAt: number;
  health: Health | null;
}) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(() => {
      setElapsed(Math.floor((Date.now() - startedAt) / 100) / 10);
    }, 100);
    return () => window.clearInterval(timer);
  }, [startedAt]);

  return (
    <section className="mx-auto w-full max-w-[1280px] px-4 pb-12 sm:px-6 lg:px-8" aria-live="polite">
      <div className="panel overflow-hidden">
        <div className="flex flex-col justify-between gap-2 border-b border-white/[0.07] px-4 py-3 sm:flex-row sm:items-center">
          <div className="flex items-center gap-2.5">
            <span className="h-1.5 w-1.5 rounded-full bg-acid pulse-dot" />
            <span className="mono text-[10px] uppercase tracking-[0.14em] text-white">
              {mode === "analyze" ? "Diagnosis in progress" : "Sandbox verification in progress"}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <StatusBadge tone="warn">{health?.model_configured ? "gemma live" : "fallback route"}</StatusBadge>
            <span className="mono text-[10px] tabular-nums text-muted">{elapsed.toFixed(1)}s</span>
          </div>
        </div>

        <div className="grid gap-4 p-4 lg:grid-cols-[1fr_320px]">
          <div className="space-y-2">
            {stages.map((stage, index) => (
              <div
                key={stage.label}
                className="agent-scan relative flex items-center gap-3 border border-white/[0.07] bg-white/[0.015] px-3 py-3"
                style={{ animationDelay: `${index * 80}ms` }}
              >
                <span className="mono w-5 text-[9px] text-faint">0{index + 1}</span>
                <span className="flex h-8 w-8 items-center justify-center border border-white/10 bg-black/20 text-muted">
                  <stage.icon size={14} />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-[12px] font-medium text-white/85">{stage.label}</p>
                  <p className="mono text-[9px] uppercase tracking-[0.1em] text-faint">{stage.note}</p>
                </div>
                <span className="mono text-[9px] uppercase tracking-[0.1em] text-faint">working</span>
              </div>
            ))}
            <p className="pt-1 text-[10px] leading-relaxed text-faint">
              {mode === "analyze"
                ? "Contract parsing and verification are real work, not a scripted animation. Gemma calls may take up to 45 seconds; a cold backend can add more."
                : "The sandbox executes every generated check against the target contract. No external services are contacted."}
            </p>
          </div>

          <div className="space-y-2">
            <div className="skeleton h-20" />
            <div className="skeleton h-14" />
            <div className="skeleton h-14" />
            <div className="skeleton h-24" />
            <div className="border border-white/[0.07] bg-black/20 p-3">
              <p className="mono text-[9px] uppercase tracking-[0.12em] text-faint">Model route</p>
              <p className="mono mt-1 text-[10px] text-white/70">
                {health ? `${health.model_provider} / ${health.model}` : "awaiting health check"}
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
