import {
  ChevronDown,
  FileJson2,
  FlaskConical,
  Loader2,
  ScanLine,
  Upload,
  Users,
  X,
} from "lucide-react";
import { useRef, useState, type DragEvent } from "react";
import { formatBytes, inspectSpec } from "../lib/spec";
import type { Consumer } from "../types";
import { Button, StatusBadge, cn } from "./ui";

interface SpecEditorProps {
  side: "legacy" | "target";
  value: string;
  onChange: (value: string) => void;
  onFileError: (error: string | null) => void;
}

function SpecEditor({ side, value, onChange, onFileError }: SpecEditorProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const inspection = inspectSpec(value);
  const isLegacy = side === "legacy";

  async function readFile(file: File | undefined) {
    onFileError(null);
    if (!file) return;
    if (file.size > 1024 * 1024) {
      onFileError("File exceeds the 1 MB UI limit. Trim the spec or use the full API.");
      return;
    }
    try {
      const text = await file.text();
      JSON.parse(text);
      onChange(text);
    } catch {
      onFileError(`${file.name} is not valid JSON.`);
    }
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    void readFile(event.dataTransfer.files[0]);
  }

  return (
    <div
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={cn(
        "relative flex min-h-0 flex-col border bg-black/20 transition-colors",
        dragging
          ? "border-acid/60 bg-acid/[0.04]"
          : isLegacy
            ? "border-cyan/15"
            : "border-acid/15",
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/[0.07] px-3 py-2.5">
        <div className="flex items-center gap-2.5">
          <span
            className={cn(
              "mono border px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-[0.14em]",
              isLegacy
                ? "border-cyan/25 bg-cyan/5 text-cyan"
                : "border-acid/25 bg-acid/5 text-acid",
            )}
          >
            {isLegacy ? "01 / legacy" : "02 / target"}
          </span>
          <span className="mono text-[10px] text-faint">
            {inspection.valid
              ? `${inspection.endpointCount} operations`
              : inspection.empty
                ? "awaiting contract"
                : "unverified"}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          {inspection.version ? (
            <StatusBadge tone="neutral">v{inspection.version}</StatusBadge>
          ) : null}
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className="mono inline-flex items-center gap-1.5 border border-white/10 px-2 py-1 text-[9px] uppercase tracking-[0.1em] text-muted transition-colors hover:border-white/25 hover:text-white"
          >
            <Upload size={10} />
            upload
          </button>
          {value ? (
            <button
              type="button"
              onClick={() => onChange("")}
              className="flex h-[23px] w-6 items-center justify-center border border-white/10 text-faint transition-colors hover:border-white/25 hover:text-white"
              aria-label={`Clear ${side} spec`}
            >
              <X size={11} />
            </button>
          ) : null}
        </div>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept=".json,application/json"
        className="hidden"
        onChange={(event) => {
          void readFile(event.target.files?.[0]);
          event.target.value = "";
        }}
      />

      <div className="relative flex-1">
        <textarea
          value={value}
          onChange={(event) => {
            onChange(event.target.value);
            onFileError(null);
          }}
          spellCheck={false}
          aria-label={`${isLegacy ? "Legacy" : "Target"} OpenAPI JSON`}
          placeholder={`Paste ${isLegacy ? "the current" : "the next"} OpenAPI JSON here, or drop a .json file.`}
          className="mono h-[286px] w-full resize-y bg-transparent p-3 text-[11px] leading-[1.65] text-[#c5d2db] outline-none placeholder:text-faint/70 focus:ring-0"
        />
        {!value ? (
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center gap-2 text-center">
            <FileJson2 size={22} className="text-faint" />
            <p className="mono text-[9px] uppercase tracking-[0.16em] text-faint">
              {isLegacy ? "legacy" : "target"} spec · JSON
            </p>
          </div>
        ) : null}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-white/[0.06] px-3 py-1.5">
        <span
          className={cn(
            "mono text-[9px] uppercase tracking-[0.12em]",
            inspection.error
              ? "text-critical"
              : inspection.valid
                ? isLegacy
                  ? "text-cyan"
                  : "text-acid"
                : "text-faint",
          )}
        >
          {inspection.error
            ? inspection.error
            : inspection.valid
              ? `${inspection.title ?? "untitled"}${inspection.openapi ? ` · OAS ${inspection.openapi}` : ""}`
              : "JSON under 1 MB"}
        </span>
        <span className="mono text-[9px] text-faint">
          {inspection.lines} lines · {formatBytes(inspection.bytes)}
        </span>
      </div>
    </div>
  );
}

interface IntakeProps {
  oldText: string;
  newText: string;
  consumersText: string;
  onOldChange: (value: string) => void;
  onNewChange: (value: string) => void;
  onConsumersChange: (value: string) => void;
  consumers: Consumer[];
  consumersError: string | null;
  onAnalyze: () => void;
  onLoadDemo: () => void;
  onDismissError: () => void;
  analyzing: boolean;
  demoLoading: boolean;
  error: string | null;
  stale: boolean;
  hasAnalysis: boolean;
}

export function Intake({
  oldText,
  newText,
  consumersText,
  onOldChange,
  onNewChange,
  onConsumersChange,
  consumers,
  consumersError,
  onAnalyze,
  onLoadDemo,
  onDismissError,
  analyzing,
  demoLoading,
  error,
  stale,
  hasAnalysis,
}: IntakeProps) {
  const [consumersOpen, setConsumersOpen] = useState(true);
  const [fileError, setFileError] = useState<string | null>(null);
  const oldInspection = inspectSpec(oldText);
  const newInspection = inspectSpec(newText);
  const canAnalyze = oldInspection.valid && newInspection.valid && !consumersError && !analyzing;

  return (
    <section id="diagnose" className="mx-auto w-full max-w-[1280px] scroll-mt-24 px-4 py-14 sm:px-6 lg:px-8 lg:py-20">
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="mb-2 flex items-center gap-3">
            <span className="mono text-[10px] font-semibold tracking-[0.16em] text-acid">01</span>
            <span className="h-px w-8 bg-acid/55" />
            <span className="eyebrow">Contract intake</span>
          </div>
          <h2 className="text-2xl font-semibold tracking-[-0.03em] text-white sm:text-3xl">
            Two contracts. One diagnosis.
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">
            Paste or drop the current and proposed OpenAPI documents. Declare consumer usage to turn
            raw diff noise into an actual blast radius.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={onLoadDemo} loading={demoLoading} disabled={analyzing}>
            Load demo fixture
          </Button>
        </div>
      </div>

      <div className="panel overflow-hidden">
        <div className="grid gap-4 p-4 lg:grid-cols-2">
          <SpecEditor
            side="legacy"
            value={oldText}
            onChange={onOldChange}
            onFileError={setFileError}
          />
          <SpecEditor
            side="target"
            value={newText}
            onChange={onNewChange}
            onFileError={setFileError}
          />
        </div>

        <div className="border-t border-white/[0.07]">
          <button
            type="button"
            onClick={() => setConsumersOpen((open) => !open)}
            className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition-colors hover:bg-white/[0.02]"
            aria-expanded={consumersOpen}
          >
            <span className="flex items-center gap-2.5">
              <Users size={14} className="text-cyan" />
              <span className="text-[13px] font-medium text-white/90">Declared consumers</span>
              <span className="mono text-[9px] uppercase tracking-[0.12em] text-faint">
                {consumers.length} attached
              </span>
              {consumersOpen ? null : (
                <span className="mono hidden text-[9px] text-faint sm:inline">open to edit</span>
              )}
            </span>
            <span className="flex items-center gap-2">
              {consumersError ? <StatusBadge tone="bad">invalid</StatusBadge> : null}
              <ChevronDown
                size={15}
                className={cn("text-faint transition-transform", consumersOpen && "rotate-180")}
              />
            </span>
          </button>
          {consumersOpen ? (
            <div className="grid gap-4 border-t border-white/[0.06] px-4 pb-4 pt-3 lg:grid-cols-[1fr_260px]">
              <div>
                <textarea
                  value={consumersText}
                  onChange={(event) => onConsumersChange(event.target.value)}
                  spellCheck={false}
                  aria-label="Declared consumers JSON"
                  placeholder='[{"name":"mobile-app","owner":"team","endpoints":["GET /v1/payments/{id}"]}]'
                  className="mono h-[132px] w-full resize-y border border-white/10 bg-black/25 p-3 text-[11px] leading-relaxed text-[#c5d2db] outline-none placeholder:text-faint/60 focus:border-cyan/35"
                />
                {consumersError ? (
                  <p className="mono mt-1.5 text-[10px] text-critical">{consumersError}</p>
                ) : null}
              </div>
              <div className="border border-white/[0.07] bg-white/[0.015] p-3">
                <p className="mono text-[9px] uppercase tracking-[0.14em] text-faint">Consumer map</p>
                <div className="mt-2 space-y-1.5">
                  {consumers.length ? (
                    consumers.map((consumer) => (
                      <div key={consumer.name} className="flex items-center justify-between gap-2">
                        <span className="mono truncate text-[10px] text-white/80">{consumer.name}</span>
                        <span className="mono text-[9px] text-faint">
                          {consumer.endpoints.length} ep
                        </span>
                      </div>
                    ))
                  ) : (
                    <p className="text-[11px] leading-relaxed text-faint">
                      No consumers declared. Findings stay spec-level.
                    </p>
                  )}
                </div>
                <p className="mt-3 border-t border-white/[0.07] pt-2 text-[10px] leading-relaxed text-faint">
                  Usage declarations only. The backend never calls consumer services.
                </p>
              </div>
            </div>
          ) : null}
        </div>

        <div className="border-t border-white/[0.07] bg-white/[0.015] px-4 py-3.5">
          {fileError ? (
            <p className="mono mb-2 text-[10px] text-critical">{fileError}</p>
          ) : null}
          {error ? (
            <div className="mb-3 flex items-start justify-between gap-3 border border-critical/25 bg-critical/[0.06] px-3 py-2">
              <p className="text-[12px] leading-relaxed text-critical/90">
                <span className="mono mr-2 text-[9px] uppercase tracking-[0.12em]">diagnosis failed</span>
                {error}
              </p>
              <button
                type="button"
                onClick={onDismissError}
                className="text-critical/70 hover:text-critical"
                aria-label="Dismiss error"
              >
                <X size={13} />
              </button>
            </div>
          ) : null}
          {stale && hasAnalysis ? (
            <div className="mb-3 border border-medium/25 bg-medium/[0.05] px-3 py-2">
              <p className="mono text-[10px] uppercase tracking-[0.1em] text-medium">
                Inputs changed — results below are from the previous diagnosis. Re-run to refresh.
              </p>
            </div>
          ) : null}
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge tone={oldInspection.valid ? "ok" : "neutral"}>
                legacy {oldInspection.valid ? "ready" : "incomplete"}
              </StatusBadge>
              <StatusBadge tone={newInspection.valid ? "ok" : "neutral"}>
                target {newInspection.valid ? "ready" : "incomplete"}
              </StatusBadge>
              <StatusBadge tone="neutral">
                <FlaskConical size={10} /> sandbox included
              </StatusBadge>
            </div>
            <Button
              onClick={onAnalyze}
              loading={analyzing}
              disabled={!canAnalyze}
              className="corner-cut min-w-[220px]"
            >
              {analyzing ? (
                <>
                  <Loader2 size={15} className="spinner" /> Agents working
                </>
              ) : (
                <>
                  <ScanLine size={15} /> Run full diagnosis
                </>
              )}
            </Button>
          </div>
          <p className="mono mt-2.5 text-right text-[9px] uppercase tracking-[0.1em] text-faint">
            JSON body limit 2 MB · no credentials required
          </p>
        </div>
      </div>
    </section>
  );
}
