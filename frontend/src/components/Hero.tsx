import {
  ArrowRight,
  Bot,
  FlaskConical,
  GitCompareArrows,
  ScanSearch,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import type { Health } from "../types";
import { sampleDescriptor } from "../data/samples";
import { Button, StatusBadge } from "./ui";

const pipeline = [
  { icon: GitCompareArrows, name: "Contract diff", note: "deterministic" },
  { icon: ScanSearch, name: "Impact map", note: "consumer topology" },
  { icon: Bot, name: "Migration strategy", note: "Gemma / fallback" },
  { icon: FlaskConical, name: "Regression tests", note: "bounded generation" },
  { icon: ShieldCheck, name: "Sandbox verify", note: "real execution" },
];

export function Hero({
  onDemo,
  demoLoading,
  health,
  hasAnalysis,
}: {
  onDemo: () => void;
  demoLoading: boolean;
  health: Health | null;
  hasAnalysis: boolean;
}) {
  const modelTone = health?.model_configured ? "ok" : "warn";
  const modelLabel = health
    ? health.model_configured
      ? `${health.model} live`
      : "fallback mode"
    : "checking model";

  return (
    <section id="top" className="relative overflow-hidden border-b border-white/[0.06]">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_65%_60%_at_75%_10%,rgba(200,244,90,0.07),transparent_65%)]" />
      <div className="relative mx-auto grid w-full max-w-[1280px] gap-12 px-4 pb-16 pt-14 sm:px-6 lg:grid-cols-[1.18fr_0.82fr] lg:gap-16 lg:px-8 lg:pb-20 lg:pt-20">
        <div className="fade-up">
          <div className="mb-6 flex flex-wrap items-center gap-3">
            <StatusBadge tone="acid">
              <span className="h-1 w-1 rounded-full bg-acid" />
              OpenAPI contract diagnostics
            </StatusBadge>
            <span className="mono text-[10px] uppercase tracking-[0.16em] text-faint">
              v1.0 / hackathon build
            </span>
          </div>

          <h1 className="max-w-[720px] text-[clamp(2.6rem,6vw,4.9rem)] font-semibold leading-[0.98] tracking-[-0.055em] text-white">
            Predict. Diagnose.
            <br />
            <span className="text-muted">Migrate.</span>{" "}
            <span className="relative inline-block text-acid">
              Verify.
              <svg
                className="absolute -bottom-2 left-0 h-2.5 w-full text-acid/60"
                viewBox="0 0 200 8"
                preserveAspectRatio="none"
                aria-hidden
              >
                <path d="M0 6 Q50 0 100 5 T200 3" fill="none" stroke="currentColor" strokeWidth="2" />
              </svg>
            </span>
          </h1>

          <p className="mt-7 max-w-[620px] text-[15px] leading-relaxed text-muted sm:text-base">
            API Doctor reads two OpenAPI contracts, finds the changes that will break real consumers,
            maps the blast radius, drafts a migration, and proves the fix in a sandbox —{" "}
            <span className="text-white/90">not just a chat response.</span>
          </p>

          <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
            <Button
              onClick={onDemo}
              loading={demoLoading}
              className="corner-cut h-12 px-6 text-[13px] uppercase tracking-[0.08em]"
            >
              {hasAnalysis ? "Re-run sample diagnosis" : "Run sample diagnosis"}
              {demoLoading ? null : <ArrowRight size={16} />}
            </Button>
            <a
              href="#diagnose"
              className="inline-flex h-12 items-center justify-center gap-2 border border-white/15 bg-white/[0.02] px-5 text-[13px] font-medium text-white/85 transition-colors hover:border-white/30 hover:bg-white/[0.05]"
            >
              Bring your own specs
            </a>
          </div>

          <div className="mt-9 flex flex-wrap items-center gap-x-7 gap-y-3 border-t border-white/[0.07] pt-6">
            {[
              ["05", "specialized agents"],
              ["100%", "deterministic diff"],
              ["real", "sandbox execution"],
              ["Gemma", "guided migration"],
            ].map(([value, label]) => (
              <div key={label} className="flex items-baseline gap-2">
                <span className="mono text-sm font-semibold text-white">{value}</span>
                <span className="text-[11px] text-faint">{label}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="fade-up fade-up-delay-1 relative">
          <div className="absolute -left-3 top-8 hidden h-16 w-px bg-gradient-to-b from-transparent via-acid/50 to-transparent lg:block" />
          <div className="panel relative overflow-hidden">
            <div className="flex items-center justify-between border-b border-white/[0.07] px-5 py-3.5">
              <div className="flex items-center gap-2.5">
                <span className="h-1.5 w-1.5 rounded-full bg-acid pulse-dot" />
                <span className="mono text-[10px] uppercase tracking-[0.18em] text-white">
                  Diagnostic pipeline
                </span>
              </div>
              <span className="mono text-[9px] uppercase tracking-[0.14em] text-faint">live system</span>
            </div>

            <div className="px-5 py-4">
              {pipeline.map((step, index) => (
                <div
                  key={step.name}
                  className="group flex items-center gap-3 border-b border-white/[0.055] py-3 last:border-0"
                >
                  <span className="mono w-5 text-[9px] text-faint">0{index + 1}</span>
                  <span className="flex h-8 w-8 items-center justify-center border border-white/10 bg-white/[0.025] text-muted transition-colors group-hover:border-acid/30 group-hover:text-acid">
                    <step.icon size={14} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] font-medium text-white/90">{step.name}</p>
                    <p className="mono text-[9px] uppercase tracking-[0.12em] text-faint">{step.note}</p>
                  </div>
                  <span className="mono text-[9px] text-faint">READY</span>
                </div>
              ))}
            </div>

            <div className="diagnostic-grid border-t border-white/[0.07] bg-black/25 px-5 py-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="mono flex items-center gap-1.5 text-[9px] uppercase tracking-[0.15em] text-acid">
                    <Sparkles size={10} /> demo fixture
                  </p>
                  <p className="mt-1.5 text-sm font-medium text-white">{sampleDescriptor.name}</p>
                  <p className="mt-1 text-[11px] leading-relaxed text-muted">
                    3 consumers · removed routes · changed units · renamed fields
                  </p>
                </div>
                <div className="hidden shrink-0 text-right sm:block">
                  <p className="mono text-[8px] uppercase tracking-[0.14em] text-faint">model route</p>
                  <p
                    className={`mono mt-1 text-[10px] uppercase tracking-[0.12em] ${
                      health?.model_configured ? "text-acid" : "text-medium"
                    }`}
                  >
                    {modelLabel}
                  </p>
                </div>
              </div>
              <div className="mt-3 flex items-center gap-2">
                <StatusBadge tone={modelTone}>{health?.model_configured ? "Gemma" : "fallback armed"}</StatusBadge>
                <StatusBadge tone="neutral">sandbox: JSON Schema</StatusBadge>
              </div>
            </div>

            <svg
              className="h-10 w-full border-t border-white/[0.05] bg-black/20 text-acid/45"
              viewBox="0 0 400 40"
              preserveAspectRatio="none"
              aria-hidden
            >
              <path
                className="ecg-line"
                d="M0 22 L42 22 L50 22 L56 10 L62 32 L68 4 L74 22 L108 22 L118 22 L124 15 L130 22 L166 22 L176 22 L182 8 L188 34 L194 3 L200 22 L238 22 L248 22 L254 14 L260 22 L298 22 L308 22 L314 7 L320 33 L326 5 L332 22 L366 22 L378 22 L384 16 L390 22 L400 22"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.4"
                strokeLinejoin="round"
              />
            </svg>
          </div>
        </div>
      </div>
    </section>
  );
}
