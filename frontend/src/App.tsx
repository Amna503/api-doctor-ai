import { ArrowUpRight, Radio, ShieldCheck, Sparkles, TerminalSquare } from "lucide-react";
import { GitHubMark } from "./components/GitHubMark";
import { useEffect, useRef, useState } from "react";
import { API_BASE_URL, REPOSITORY_URL, analyzeSpecs, checkHealth, errorMessage, verifySpecs } from "./api";
import { AnalysisView } from "./components/AnalysisView";
import { Hero } from "./components/Hero";
import { ImpactSection } from "./components/ImpactSection";
import { Intake } from "./components/Intake";
import { LoadingState } from "./components/LoadingState";
import { MigrationSection } from "./components/MigrationSection";
import { SiteHeader, type HealthState } from "./components/SiteHeader";
import { TraceDrawer } from "./components/TraceDrawer";
import { VerificationSection } from "./components/VerificationSection";
import {
  sampleConsumersText,
  sampleNewText,
  sampleOldText,
} from "./data/samples";
import { inspectSpec, parseConsumers, parseSpecDocument } from "./lib/spec";
import type {
  AnalysisResult,
  AnalyzePayload,
  Consumer,
  Health,
  VerificationResult,
} from "./types";

interface Snapshot {
  old: string;
  new: string;
  consumers: string;
}

export default function App() {
  const [oldText, setOldText] = useState("");
  const [newText, setNewText] = useState("");
  const [consumersText, setConsumersText] = useState("");
  const [health, setHealth] = useState<Health | null>(null);
  const [healthState, setHealthState] = useState<HealthState>("checking");
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [verification, setVerification] = useState<VerificationResult | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);
  const [verifyMode, setVerifyMode] = useState<"standard" | "patch" | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [verifyError, setVerifyError] = useState<string | null>(null);
  const [tracesOpen, setTracesOpen] = useState(false);
  const [diagnosedSnapshot, setDiagnosedSnapshot] = useState<Snapshot | null>(null);
  const [sourcePayload, setSourcePayload] = useState<AnalyzePayload | null>(null);
  const [busyStarted, setBusyStarted] = useState(() => Date.now());
  const resultRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await checkHealth();
        if (!cancelled) {
          setHealth(data);
          setHealthState("online");
        }
      } catch {
        if (!cancelled) setHealthState("offline");
      }
    }
    void load();
    const timer = window.setInterval(load, 30000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const consumersParsed = parseConsumers(consumersText);
  const consumers: Consumer[] = consumersParsed.consumers;
  const stale = Boolean(
    analysis &&
      diagnosedSnapshot &&
      (oldText !== diagnosedSnapshot.old ||
        newText !== diagnosedSnapshot.new ||
        consumersText !== diagnosedSnapshot.consumers),
  );

  function invalidateVerification() {
    setVerification(null);
    setVerifyError(null);
  }

  function handleOldChange(value: string) {
    setOldText(value);
    setAnalyzeError(null);
    invalidateVerification();
  }

  function handleNewChange(value: string) {
    setNewText(value);
    setAnalyzeError(null);
    invalidateVerification();
  }

  function handleConsumersChange(value: string) {
    setConsumersText(value);
    setAnalyzeError(null);
    invalidateVerification();
  }

  function loadDemoInputs() {
    setOldText(sampleOldText);
    setNewText(sampleNewText);
    setConsumersText(sampleConsumersText);
    setAnalyzeError(null);
    invalidateVerification();
  }

  async function runDiagnosis(
    oldValue: string,
    newValue: string,
    consumerValue: string,
    demo = false,
  ): Promise<boolean> {
    setAnalyzeError(null);
    setVerifyError(null);
    const oldInspection = inspectSpec(oldValue);
    const newInspection = inspectSpec(newValue);
    if (!oldInspection.valid || !newInspection.valid) {
      setAnalyzeError(
        !oldInspection.valid
          ? oldInspection.empty
            ? "Paste the legacy OpenAPI document first."
            : `Legacy spec: ${oldInspection.error}`
          : !newInspection.valid
            ? newInspection.empty
              ? "Paste the target OpenAPI document."
              : `Target spec: ${newInspection.error}`
            : "Both specs must be valid.",
      );
      return false;
    }
    const consumerParsed = parseConsumers(consumerValue);
    if (consumerParsed.error) {
      setAnalyzeError(`Consumers: ${consumerParsed.error}`);
      return false;
    }
    let payload: AnalyzePayload;
    try {
      payload = {
        old_spec: parseSpecDocument(oldValue),
        new_spec: parseSpecDocument(newValue),
        consumers: consumerParsed.consumers,
      };
    } catch (error) {
      setAnalyzeError(errorMessage(error));
      return false;
    }

    setAnalyzing(true);
    setDemoLoading(demo);
    setBusyStarted(Date.now());
    try {
      const result = await analyzeSpecs(payload);
      setAnalysis(result);
      setSourcePayload(payload);
      setDiagnosedSnapshot({ old: oldValue, new: newValue, consumers: consumerValue });
      setVerification(null);
      window.setTimeout(() => {
        resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 120);
      return true;
    } catch (error) {
      setAnalyzeError(errorMessage(error));
      return false;
    } finally {
      setAnalyzing(false);
      setDemoLoading(false);
    }
  }

  async function handleDemo() {
    loadDemoInputs();
    await runDiagnosis(sampleOldText, sampleNewText, sampleConsumersText, true);
  }

  async function handleVerify(applyPatch: boolean) {
    if (!analysis || !sourcePayload) return;
    if (stale) {
      setVerifyError("Inputs changed since this diagnosis. Re-run the diagnosis before verifying.");
      return;
    }
    setVerifyMode(applyPatch ? "patch" : "standard");
    setVerifyError(null);
    try {
      const result = await verifySpecs({
        ...sourcePayload,
        apply_compatibility_patch: applyPatch,
      });
      setVerification(result);
    } catch (error) {
      setVerifyError(errorMessage(error));
    } finally {
      setVerifyMode(null);
    }
  }

  const year = new Date().getFullYear();

  return (
    <div className="min-h-screen">
      <a
        href="#diagnose"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:bg-acid focus:px-3 focus:py-2 focus:text-ink"
      >
        Skip to diagnosis
      </a>
      <SiteHeader health={health} healthState={healthState} repositoryUrl={REPOSITORY_URL} />

      <main>
        <Hero onDemo={handleDemo} demoLoading={demoLoading} health={health} hasAnalysis={Boolean(analysis)} />

        <Intake
          oldText={oldText}
          newText={newText}
          consumersText={consumersText}
          onOldChange={handleOldChange}
          onNewChange={handleNewChange}
          onConsumersChange={handleConsumersChange}
          consumers={consumers}
          consumersError={consumersParsed.error}
          onAnalyze={() => void runDiagnosis(oldText, newText, consumersText)}
          onLoadDemo={loadDemoInputs}
          onDismissError={() => setAnalyzeError(null)}
          analyzing={analyzing}
          demoLoading={demoLoading}
          error={analyzeError}
          stale={stale}
          hasAnalysis={Boolean(analysis)}
        />

        {analyzing ? (
          <LoadingState mode="analyze" startedAt={busyStarted} health={health} />
        ) : null}

        <div ref={resultRef}>
          {analysis ? (
            <>
              <AnalysisView
                key={analysis.analysis_id}
                result={analysis}
                onOpenTraces={() => setTracesOpen(true)}
              />
              <ImpactSection impact={analysis.impact} />
              <MigrationSection plan={analysis.migration} />
              <VerificationSection
                analysis={analysis}
                verification={verification}
                verifyMode={verifyMode}
                error={verifyError}
                onVerify={(applyPatch) => void handleVerify(applyPatch)}
                onOpenTraces={() => setTracesOpen(true)}
              />
            </>
          ) : (
            <section className="mx-auto w-full max-w-[1280px] px-4 pb-16 sm:px-6 lg:px-8">
              <div className="grid gap-px overflow-hidden border border-white/[0.07] bg-white/[0.07] md:grid-cols-3">
                {[
                  {
                    icon: TerminalSquare,
                    title: "Deterministic findings",
                    body: "Rule-based diffing produces every breaking signal. The report is reproducible and evidence-cited.",
                  },
                  {
                    icon: Sparkles,
                    title: "Bounded AI guidance",
                    body: "Gemma drafts migration steps with a strict timeout and schema validation. Fallback keeps output complete.",
                  },
                  {
                    icon: ShieldCheck,
                    title: "Executed, not imagined",
                    body: "Regression checks run against the target contract. Pass, fail, and residual risk are actual sandbox outputs.",
                  },
                ].map((item) => (
                  <div key={item.title} className="bg-panel px-5 py-6">
                    <item.icon size={17} className="text-acid" />
                    <p className="mt-3 text-sm font-semibold text-white">{item.title}</p>
                    <p className="mt-1.5 text-[12px] leading-relaxed text-muted">{item.body}</p>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>

        <section className="border-t border-white/[0.06]">
          <div className="mx-auto grid w-full max-w-[1280px] gap-4 px-4 py-8 sm:px-6 md:grid-cols-3 lg:px-8">
            <div>
              <p className="mono text-[9px] uppercase tracking-[0.16em] text-acid">Method / 01</p>
              <p className="mt-2 text-[12px] font-medium text-white/85">Deterministic first</p>
              <p className="mt-1 text-[11px] leading-relaxed text-faint">
                The contract diff, impact graph, and test scaffold never depend on a language model.
              </p>
            </div>
            <div>
              <p className="mono text-[9px] uppercase tracking-[0.16em] text-acid">Method / 02</p>
              <p className="mt-2 text-[12px] font-medium text-white/85">AI is bounded</p>
              <p className="mt-1 text-[11px] leading-relaxed text-faint">
                Gemma only drafts guidance, with retries, timeouts, and schema validation. Fallback is
                labelled, never hidden.
              </p>
            </div>
            <div>
              <p className="mono text-[9px] uppercase tracking-[0.16em] text-acid">Method / 03</p>
              <p className="mt-2 text-[12px] font-medium text-white/85">Proof over prose</p>
              <p className="mt-1 text-[11px] leading-relaxed text-faint">
                Verification executes real checks and reports failures. Nothing is marked verified
                without a sandbox run.
              </p>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-white/[0.07] bg-black/20">
        <div className="mx-auto flex w-full max-w-[1280px] flex-col gap-4 px-4 py-6 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
          <div>
            <p className="mono text-[9px] uppercase tracking-[0.16em] text-faint">
              API Doctor AI · contract diagnostics
            </p>
            <p className="mt-1.5 max-w-2xl text-[10px] leading-relaxed text-faint/80">
              Hackathon MVP. Findings are deterministic; AI suggestions may be wrong. Sandbox results
              are simulated against the submitted contract — no production traffic is touched.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-4">
            <span className="mono flex items-center gap-1.5 text-[9px] uppercase tracking-[0.1em] text-faint">
              <Radio size={10} className={healthState === "online" ? "text-acid" : "text-faint"} />
              {healthState === "online" ? "backend reachable" : healthState === "checking" ? "checking backend" : "backend offline"}
            </span>
            <a
              href={REPOSITORY_URL}
              target="_blank"
              rel="noreferrer"
              className="mono flex items-center gap-1.5 text-[9px] uppercase tracking-[0.1em] text-muted transition-colors hover:text-acid"
            >
              <GitHubMark size={11} /> repository <ArrowUpRight size={10} />
            </a>
            <a
              href={`${API_BASE_URL || ""}/docs`}
              target="_blank"
              rel="noreferrer"
              className="mono flex items-center gap-1.5 text-[9px] uppercase tracking-[0.1em] text-muted transition-colors hover:text-acid"
            >
              api docs <ArrowUpRight size={10} />
            </a>
            <span className="mono text-[9px] text-faint">© {year}</span>
          </div>
        </div>
      </footer>

      <TraceDrawer
        open={tracesOpen}
        onClose={() => setTracesOpen(false)}
        analysis={analysis}
        verification={verification}
      />
    </div>
  );
}
