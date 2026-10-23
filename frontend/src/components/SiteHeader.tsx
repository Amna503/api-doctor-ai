import { Activity, Radio } from "lucide-react";
import { GitHubMark } from "./GitHubMark";
import type { Health } from "../types";

export type HealthState = "checking" | "online" | "offline";

const links = [
  { href: "#diagnose", label: "Diagnose", number: "02" },
  { href: "#impact", label: "Impact", number: "03" },
  { href: "#migrate", label: "Migrate", number: "04" },
  { href: "#verify", label: "Verify", number: "05" },
];

export function SiteHeader({
  health,
  healthState,
  repositoryUrl,
}: {
  health: Health | null;
  healthState: HealthState;
  repositoryUrl: string;
}) {
  const statusLabel =
    healthState === "online" ? "Engine online" : healthState === "checking" ? "Syncing" : "Engine offline";
  const dot =
    healthState === "online" ? "bg-acid" : healthState === "checking" ? "bg-medium" : "bg-critical";

  return (
    <header className="sticky top-0 z-40 border-b border-white/[0.07] bg-ink/85 backdrop-blur-xl">
      <div className="mx-auto flex h-[68px] w-full max-w-[1280px] items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <a href="#top" className="group flex min-w-0 items-center gap-3">
          <span className="corner-cut-sm relative flex h-9 w-9 shrink-0 items-center justify-center border border-acid/40 bg-acid/10 text-acid">
            <Activity size={19} strokeWidth={2.2} />
            <span className="absolute right-0 top-0 h-1.5 w-1.5 bg-acid" />
          </span>
          <span className="flex min-w-0 flex-col leading-none">
            <span className="flex items-baseline gap-1.5 text-[15px] font-bold tracking-[0.13em] text-white">
              API DOCTOR
              <span className="text-acid">AI</span>
            </span>
            <span className="mono mt-1 hidden text-[8px] uppercase tracking-[0.24em] text-faint sm:block">
              Contract diagnostics unit
            </span>
          </span>
        </a>

        <nav className="hidden items-center gap-1 lg:flex" aria-label="Sections">
          {links.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="group flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-muted transition-colors hover:text-white"
            >
              <span className="mono text-[9px] text-faint transition-colors group-hover:text-acid">
                {link.number}
              </span>
              {link.label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-2 sm:gap-3">
          <div
            className="flex items-center gap-2 border border-white/10 bg-white/[0.025] px-2.5 py-1.5"
            title={
              health
                ? `${health.model_provider} · ${health.model} · ${health.environment}`
                : "Contacting the diagnostic backend"
            }
          >
            <span className={`h-1.5 w-1.5 rounded-full ${dot} ${healthState === "online" ? "pulse-dot" : ""}`} />
            <span className="mono hidden text-[9px] uppercase tracking-[0.14em] text-muted sm:inline">
              {statusLabel}
            </span>
            <Radio size={11} className="text-faint sm:hidden" />
          </div>
          <a
            href={repositoryUrl}
            target="_blank"
            rel="noreferrer"
            className="flex h-8 w-8 items-center justify-center border border-white/10 bg-white/[0.025] text-muted transition-colors hover:border-white/25 hover:text-white"
            aria-label="Open the GitHub repository"
          >
            <GitHubMark size={15} />
          </a>
        </div>
      </div>
    </header>
  );
}
