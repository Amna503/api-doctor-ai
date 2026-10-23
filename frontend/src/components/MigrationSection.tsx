import {
  AlertTriangle,
  Bot,
  ChevronDown,
  FileCode2,
  GitCommitVertical,
  Info,
  Sparkles,
} from "lucide-react";
import { useState } from "react";
import { formatDateTime } from "../lib/format";
import type { MigrationPlan } from "../types";
import {
  CodeBlock,
  CopyButton,
  SectionHeading,
  StatusBadge,
  cn,
} from "./ui";

export function MigrationSection({ plan }: { plan: MigrationPlan }) {
  const [openStep, setOpenStep] = useState<string | null>(plan.steps[0]?.id ?? null);
  const isGemma = plan.source === "gemma";
  const averageConfidence = plan.steps.length
    ? Math.round(
        (plan.steps.reduce((sum, step) => sum + step.confidence, 0) / plan.steps.length) * 100,
      )
    : 0;

  return (
    <section id="migrate" className="border-y border-white/[0.06] bg-white/[0.012]">
      <div className="mx-auto w-full max-w-[1280px] scroll-mt-24 px-4 py-14 sm:px-6 lg:px-8 lg:py-20">
        <SectionHeading
          number="04"
          eyebrow="Migration strategy"
          title="A route through the breakage."
          description="Evidence-cited steps, ordered by dependency. Gemma guides when configured; the deterministic fallback keeps the workflow complete regardless."
          action={
            <StatusBadge tone={isGemma ? "ok" : "warn"}>
              {isGemma ? <Sparkles size={10} /> : <Bot size={10} />}
              {isGemma ? "gemma guidance" : "deterministic fallback"}
            </StatusBadge>
          }
        />

        <div className="panel overflow-hidden">
          <div className="flex flex-col justify-between gap-2 border-b border-white/[0.07] px-4 py-3 sm:flex-row sm:items-center">
            <div className="flex flex-wrap items-center gap-2">
              <span className="mono text-[10px] uppercase tracking-[0.14em] text-white">
                Migration plan
              </span>
              <StatusBadge tone="neutral">{plan.model}</StatusBadge>
              <StatusBadge tone="neutral">{plan.steps.length} steps</StatusBadge>
              <StatusBadge tone="neutral">avg {averageConfidence}% confidence</StatusBadge>
            </div>
            <div className="flex items-center gap-3">
              <span className="mono text-[9px] text-faint">{plan.prompt_version}</span>
              <span className="mono text-[9px] text-faint">{formatDateTime(plan.generated_at)}</span>
              <CopyButton text={JSON.stringify(plan, null, 2)} label="Copy plan" />
            </div>
          </div>

          <div className="grid gap-5 p-4 lg:grid-cols-[1.35fr_0.65fr] lg:p-5">
            <div>
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center border border-acid/25 bg-acid/[0.06] text-acid">
                  <GitCommitVertical size={14} />
                </span>
                <p className="text-[13px] font-semibold text-white">Strategy</p>
              </div>
              <p className="mt-3 text-lg font-medium leading-snug tracking-[-0.02em] text-white/95">
                {plan.summary}
              </p>
              <p className="mt-3 text-[13px] leading-relaxed text-muted">{plan.strategy}</p>
            </div>

            <div className="border border-white/[0.075] bg-black/20 p-3.5">
              <p className="mono text-[9px] uppercase tracking-[0.14em] text-faint">Provenance</p>
              <dl className="mt-2 space-y-2">
                {[
                  ["Source", isGemma ? "Gemma via Google AI Studio" : "Deterministic fallback"],
                  ["Model", plan.model],
                  ["Prompt", plan.prompt_version],
                  ["Generated", formatDateTime(plan.generated_at)],
                ].map(([label, value]) => (
                  <div key={label} className="flex items-start justify-between gap-3">
                    <dt className="mono text-[9px] uppercase tracking-[0.1em] text-faint">{label}</dt>
                    <dd className="mono text-right text-[9px] text-white/75">{value}</dd>
                  </div>
                ))}
              </dl>
              <div className="mt-3 flex items-start gap-2 border-t border-white/[0.07] pt-2.5">
                <Info size={12} className="mt-0.5 shrink-0 text-faint" />
                <p className="text-[10px] leading-relaxed text-faint">
                  Suggestions only. The diff, tests, and sandbox outputs remain authoritative.
                </p>
              </div>
            </div>
          </div>

          {plan.warnings.length ? (
            <div className="mx-4 mb-4 border border-medium/25 bg-medium/[0.05] p-3 lg:mx-5">
              <p className="mono flex items-center gap-2 text-[9px] uppercase tracking-[0.14em] text-medium">
                <AlertTriangle size={11} /> Warnings · {plan.warnings.length}
              </p>
              <ul className="mt-2 space-y-1">
                {plan.warnings.map((warning) => (
                  <li key={warning} className="flex items-start gap-2 text-[11px] leading-relaxed text-muted">
                    <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-medium" />
                    {warning}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <div className="border-t border-white/[0.07] p-4 lg:p-5">
            <div className="mb-3 flex items-center justify-between">
              <p className="mono text-[9px] uppercase tracking-[0.14em] text-faint">
                Migration sequence
              </p>
              <p className="mono text-[9px] uppercase tracking-[0.14em] text-faint">
                {openStep ? "1 step expanded" : "all collapsed"}
              </p>
            </div>
            <div className="space-y-2">
              {plan.steps.map((step, index) => {
                const open = openStep === step.id;
                return (
                  <div
                    key={step.id}
                    className={cn(
                      "border transition-colors",
                      open
                        ? "border-white/20 bg-white/[0.025]"
                        : "border-white/[0.065] bg-white/[0.012] hover:border-white/15",
                    )}
                  >
                    <button
                      type="button"
                      onClick={() => setOpenStep(open ? null : step.id)}
                      className="flex w-full items-start gap-3 px-3 py-3 text-left"
                      aria-expanded={open}
                    >
                      <span
                        className={cn(
                          "mono flex h-7 w-7 shrink-0 items-center justify-center border text-[10px]",
                          open
                            ? "border-acid/40 bg-acid/10 text-acid"
                            : "border-white/12 bg-black/20 text-faint",
                        )}
                      >
                        {String(index + 1).padStart(2, "0")}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="text-[13px] font-medium leading-snug text-white/90">
                          {step.title}
                        </p>
                        <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                          {step.finding_ids.map((id) => (
                            <span
                              key={id}
                              className="mono border border-white/10 bg-black/20 px-1.5 py-0.5 text-[8px] uppercase tracking-[0.08em] text-faint"
                            >
                              {id}
                            </span>
                          ))}
                        </div>
                      </div>
                      <div className="flex shrink-0 flex-col items-end gap-1.5">
                        <span className="mono text-[9px] text-faint">
                          {Math.round(step.confidence * 100)}% conf
                        </span>
                        <div className="h-0.5 w-16 overflow-hidden bg-white/10">
                          <div
                            className="h-full bg-acid/80"
                            style={{ width: `${Math.round(step.confidence * 100)}%` }}
                          />
                        </div>
                        <ChevronDown
                          size={14}
                          className={cn("mt-1 text-faint transition-transform", open && "rotate-180")}
                        />
                      </div>
                    </button>

                    {open ? (
                      <div className="border-t border-white/[0.07] px-3 py-3">
                        <p className="text-[12px] leading-relaxed text-muted">{step.detail}</p>
                        {step.notes ? (
                          <p className="mt-2 border-l border-cyan/35 pl-3 text-[11px] leading-relaxed text-cyan/75">
                            {step.notes}
                          </p>
                        ) : null}
                        {step.code_before || step.code_after ? (
                          <div className="mt-3 grid gap-2 lg:grid-cols-2">
                            {step.code_before ? (
                              <CodeBlock code={step.code_before} label="before" tone="before" maxHeight="210px" />
                            ) : null}
                            {step.code_after ? (
                              <CodeBlock code={step.code_after} label="after" tone="after" maxHeight="210px" />
                            ) : null}
                          </div>
                        ) : (
                          <p className="mono mt-3 flex items-center gap-2 text-[9px] uppercase tracking-[0.1em] text-faint">
                            <FileCode2 size={11} /> no code snippet attached
                          </p>
                        )}
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
            {plan.steps.length === 0 ? (
              <div className="border border-white/[0.07] bg-black/20 px-4 py-8 text-center">
                <p className="text-sm text-muted">No migration steps were produced.</p>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </section>
  );
}
