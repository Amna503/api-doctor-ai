import { Check, Copy, Loader2 } from "lucide-react";
import { useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import type { RiskLevel, Severity } from "../types";

export function cn(...values: Array<string | false | null | undefined>): string {
  return values.filter(Boolean).join(" ");
}

const severityStyles: Record<Severity, string> = {
  critical: "border-critical/35 bg-critical/10 text-critical",
  high: "border-high/35 bg-high/10 text-high",
  medium: "border-medium/35 bg-medium/10 text-medium",
  low: "border-low/35 bg-low/10 text-low",
  info: "border-white/12 bg-white/5 text-info",
};

const riskStyles: Record<RiskLevel, string> = {
  ...severityStyles,
  clean: "border-acid/35 bg-acid/10 text-acid",
};

export function SeverityBadge({
  severity,
  className,
}: {
  severity: Severity | RiskLevel;
  className?: string;
}) {
  const style = severity in riskStyles ? riskStyles[severity as RiskLevel] : riskStyles.info;
  return (
    <span
      className={cn(
        "mono inline-flex items-center gap-1.5 border px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.14em]",
        style,
        className,
      )}
    >
      <span className="h-1 w-1 rounded-full bg-current" />
      {severity}
    </span>
  );
}

export function StatusBadge({
  tone,
  children,
  className,
}: {
  tone: "ok" | "warn" | "bad" | "neutral" | "acid";
  children: ReactNode;
  className?: string;
}) {
  const tones = {
    ok: "border-acid/30 bg-acid/10 text-acid",
    acid: "border-acid/35 bg-acid/10 text-acid",
    warn: "border-medium/30 bg-medium/10 text-medium",
    bad: "border-critical/30 bg-critical/10 text-critical",
    neutral: "border-white/10 bg-white/5 text-muted",
  };
  return (
    <span
      className={cn(
        "mono inline-flex items-center gap-1.5 border px-2 py-0.5 text-[10px] uppercase tracking-[0.14em]",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function MethodTag({ method }: { method: string }) {
  const colors: Record<string, string> = {
    GET: "text-cyan border-cyan/25 bg-cyan/5",
    POST: "text-acid border-acid/25 bg-acid/5",
    PUT: "text-medium border-medium/25 bg-medium/5",
    PATCH: "text-high border-high/25 bg-high/5",
    DELETE: "text-critical border-critical/25 bg-critical/5",
  };
  return (
    <span
      className={cn(
        "mono inline-flex min-w-[48px] justify-center border px-1.5 py-0.5 text-[10px] font-semibold tracking-[0.08em]",
        colors[method] ?? "text-muted border-white/10 bg-white/5",
      )}
    >
      {method}
    </span>
  );
}

type ButtonVariant = "primary" | "outline" | "ghost" | "danger";

export function Button({
  children,
  variant = "primary",
  loading = false,
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  loading?: boolean;
}) {
  const styles: Record<ButtonVariant, string> = {
    primary:
      "bg-acid text-ink hover:bg-acid-strong border-acid shadow-[0_0_32px_rgba(200,244,90,0.14)]",
    outline: "border-white/15 bg-white/[0.03] text-white hover:border-white/30 hover:bg-white/[0.06]",
    ghost: "border-transparent bg-transparent text-muted hover:bg-white/5 hover:text-white",
    danger: "border-critical/35 bg-critical/10 text-critical hover:bg-critical/15",
  };
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 border px-4 py-2.5 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-45",
        styles[variant],
        className,
      )}
      disabled={loading || props.disabled}
      {...props}
    >
      {loading ? <Loader2 size={16} className="spinner" aria-hidden /> : null}
      {children}
    </button>
  );
}

export function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  }
  return (
    <button
      type="button"
      onClick={copy}
      className="mono inline-flex items-center gap-1.5 border border-white/10 bg-black/20 px-2 py-1 text-[10px] uppercase tracking-[0.12em] text-muted transition-colors hover:border-white/25 hover:text-white"
    >
      {copied ? <Check size={11} /> : <Copy size={11} />}
      {copied ? "Copied" : label}
    </button>
  );
}

export function CodeBlock({
  code,
  label,
  tone = "neutral",
  maxHeight = "260px",
}: {
  code: string;
  label?: string;
  tone?: "neutral" | "before" | "after";
  maxHeight?: string;
}) {
  const tones = {
    neutral: "border-white/10 bg-[#070b0e]",
    before: "border-critical/20 bg-critical/[0.035]",
    after: "border-acid/20 bg-acid/[0.035]",
  };
  return (
    <div className={cn("overflow-hidden border", tones[tone])}>
      <div className="flex items-center justify-between border-b border-white/8 px-3 py-1.5">
        <span className="mono text-[9px] uppercase tracking-[0.16em] text-faint">
          {label ?? "code"}
        </span>
        <CopyButton text={code} />
      </div>
      <pre
        className="code-scroll mono overflow-auto p-3 text-[11px] leading-relaxed text-[#c8d4dc]"
        style={{ maxHeight }}
      >
        <code>{code}</code>
      </pre>
    </div>
  );
}

export function SectionHeading({
  number,
  eyebrow,
  title,
  description,
  action,
}: {
  number: string;
  eyebrow: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <div className="mb-2 flex items-center gap-3">
          <span className="mono text-[10px] font-semibold tracking-[0.16em] text-acid">
            {number}
          </span>
          <span className="h-px w-8 bg-acid/55" />
          <span className="eyebrow">{eyebrow}</span>
        </div>
        <h2 className="text-2xl font-semibold tracking-[-0.03em] text-white sm:text-3xl">{title}</h2>
        {description ? (
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">{description}</p>
        ) : null}
      </div>
      {action}
    </div>
  );
}

export function ScoreRing({
  score,
  level,
  verified,
  size = 132,
}: {
  score: number;
  level: RiskLevel;
  verified: boolean;
  size?: number;
}) {
  const radius = (size - 14) / 2;
  const circumference = 2 * Math.PI * radius;
  const dash = (Math.max(0, Math.min(100, score)) / 100) * circumference;
  const colors: Record<string, string> = {
    critical: "#ff5470",
    high: "#ff8a45",
    medium: "#f4c95d",
    low: "#6ca8ff",
    info: "#8b98a9",
    clean: "#c8f45a",
  };
  const stroke = colors[level] ?? "#8b98a9";
  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.07)"
          strokeWidth="7"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={stroke}
          strokeWidth="7"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${circumference}`}
          style={{ transition: "stroke-dasharray 700ms cubic-bezier(0.22,1,0.36,1)" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-semibold tracking-[-0.04em]" style={{ color: stroke }}>
          {score}
        </span>
        <span className="mono text-[9px] uppercase tracking-[0.16em] text-faint">
          {verified ? "risk score" : "pre-check"}
        </span>
      </div>
    </div>
  );
}

export function EmptyIcon({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto flex h-11 w-11 items-center justify-center border border-white/10 bg-white/[0.03] text-muted">
      {children}
    </div>
  );
}
