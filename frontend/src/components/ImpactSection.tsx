import { Box, Boxes, Grid2X2, Network, Users } from "lucide-react";
import { Suspense, lazy, useMemo, useState } from "react";
import type { GraphEdge, GraphNode, ImpactReport } from "../types";
import { SectionHeading, SeverityBadge, StatusBadge, cn } from "./ui";

const ImpactGraph3D = lazy(() => import("./ImpactGraph3D"));

const severityColor: Record<string, string> = {
  critical: "#ff5470",
  high: "#ff8a45",
  medium: "#f4c95d",
  low: "#6ca8ff",
  info: "#8b98a9",
};

function shortPath(path: string): string {
  return path.replace(/^\/v\d+/, "").length > 28
    ? `${path.replace(/^\/v\d+/, "").slice(0, 27)}…`
    : path.replace(/^\/v\d+/, "");
}

function ImpactMap2D({ nodes, edges }: { nodes: GraphNode[]; edges: GraphEdge[] }) {
  const layout = useMemo(() => {
    const consumers = nodes.filter((node) => node.kind === "consumer");
    const endpoints = nodes.filter((node) => node.kind === "endpoint");
    const width = 960;
    const height = 520;
    const consumerX = 150;
    const endpointX = 748;
    const consumerY = new Map<string, number>();
    const endpointY = new Map<string, number>();

    consumers.forEach((node, index) => {
      const gap = height / (consumers.length + 1);
      consumerY.set(node.id, gap * (index + 1));
    });
    endpoints.forEach((node, index) => {
      const gap = endpoints.length > 1 ? (height - 96) / (endpoints.length - 1) : 0;
      endpointY.set(node.id, endpoints.length > 1 ? 48 + gap * index : height / 2);
    });

    return { consumers, endpoints, width, height, consumerX, endpointX, consumerY, endpointY };
  }, [nodes]);

  if (!nodes.length) {
    return (
      <div className="flex h-[430px] items-center justify-center border border-white/[0.07] bg-black/25">
        <p className="text-sm text-faint">No topology to render for this contract pair.</p>
      </div>
    );
  }

  const endpointById = new Map(layout.endpoints.map((node) => [node.id, node]));

  return (
    <div className="overflow-x-auto border border-white/[0.07] bg-[#070b0e]">
      <svg
        viewBox={`0 0 ${layout.width} ${layout.height}`}
        className="h-auto min-h-[430px] w-full min-w-[720px]"
        role="img"
        aria-label="Consumer to endpoint impact graph"
      >
        <defs>
          <pattern id="impact-grid" width="24" height="24" patternUnits="userSpaceOnUse">
            <path d="M 24 0 L 0 0 0 24" fill="none" stroke="rgba(200,244,90,0.05)" strokeWidth="1" />
          </pattern>
        </defs>
        <rect width={layout.width} height={layout.height} fill="url(#impact-grid)" />

        <text x={layout.consumerX} y={22} textAnchor="middle" className="fill-[#5c6c78] font-mono text-[9px] uppercase tracking-[0.16em]">
          declared consumers
        </text>
        <text x={layout.endpointX} y={22} textAnchor="middle" className="fill-[#5c6c78] font-mono text-[9px] uppercase tracking-[0.16em]">
          affected endpoints
        </text>

        {edges.map((edge, index) => {
          const sourceY = layout.consumerY.get(edge.source);
          const targetY = layout.endpointY.get(edge.target);
          if (sourceY === undefined || targetY === undefined) return null;
          const endpoint = endpointById.get(edge.target);
          const color = severityColor[endpoint?.severity ?? "info"];
          const path = `M 238 ${sourceY} C 420 ${sourceY}, 560 ${targetY}, 738 ${targetY}`;
          return (
            <g key={`${edge.source}-${edge.target}-${index}`}>
              <path d={path} fill="none" stroke={color} strokeOpacity={0.28} strokeWidth={1} strokeDasharray="3 4" />
              <circle r={2} fill={color} fillOpacity={0.8}>
                <animateMotion dur={`${5 + (index % 4)}s`} repeatCount="indefinite" path={path} />
              </circle>
            </g>
          );
        })}

        {layout.consumers.map((node) => {
          const y = layout.consumerY.get(node.id) ?? 0;
          return (
            <g key={node.id}>
              <rect
                x={layout.consumerX - 78}
                y={y - 22}
                width={156}
                height={44}
                fill="#0d161b"
                stroke="#5ce1e6"
                strokeOpacity={0.35}
              />
              <rect x={layout.consumerX - 78} y={y - 22} width={3} height={44} fill="#5ce1e6" />
              <text x={layout.consumerX - 64} y={y - 5} className="fill-[#e6edf1] font-sans text-[11px] font-medium">
                {node.label.length > 19 ? `${node.label.slice(0, 19)}…` : node.label}
              </text>
              <text x={layout.consumerX - 64} y={y + 10} className="fill-[#5c6c78] font-mono text-[8px] uppercase tracking-[0.12em]">
                consumer · {String(node.meta.endpoint_count ?? "")} endpoints
              </text>
            </g>
          );
        })}

        {layout.endpoints.map((node) => {
          const y = layout.endpointY.get(node.id) ?? 0;
          const color = severityColor[node.severity ?? "info"];
          const [method, ...rest] = node.label.split(" ");
          const path = rest.join(" ");
          return (
            <g key={node.id}>
              <title>{node.label}</title>
              <circle cx={layout.endpointX} cy={y} r={5} fill={color} fillOpacity={0.85} />
              <circle cx={layout.endpointX} cy={y} r={9} fill="none" stroke={color} strokeOpacity={0.25} />
              <text x={layout.endpointX - 18} y={y - 1} textAnchor="end" className="fill-[#c6d2da] font-mono text-[9px]">
                {shortPath(path)}
              </text>
              <text x={layout.endpointX - 18} y={y + 10} textAnchor="end" className="fill-[#5c6c78] font-mono text-[8px] tracking-[0.08em]">
                {method}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export function ImpactSection({ impact }: { impact: ImpactReport }) {
  const [mode, setMode] = useState<"3d" | "2d">(() =>
    typeof window !== "undefined" && window.matchMedia("(max-width: 767px)").matches ? "2d" : "3d",
  );

  return (
    <section id="impact" className="mx-auto w-full max-w-[1280px] scroll-mt-24 px-4 py-14 sm:px-6 lg:px-8 lg:py-20">
      <SectionHeading
        number="03"
        eyebrow="Impact map"
        title="Follow the blast radius."
        description="Declared consumer usage becomes a dependency topology. Consumers, endpoints, and severity — nothing inferred from traffic we cannot see."
        action={
          <div className="flex items-center gap-2">
            <StatusBadge tone="neutral">
              <Users size={10} /> {impact.consumers.length} consumers
            </StatusBadge>
            <StatusBadge tone="neutral">
              <Network size={10} /> {impact.affected_endpoints.length} endpoints
            </StatusBadge>
          </div>
        }
      />

      <div className="panel overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-white/[0.07] px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2">
            <Boxes size={15} className="text-cyan" />
            <span className="mono text-[10px] uppercase tracking-[0.14em] text-white">
              Consumer → endpoint topology
            </span>
            <StatusBadge tone="neutral">declared usage</StatusBadge>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden items-center gap-2 md:flex">
              {["critical", "high", "medium", "low"].map((severity) => (
                <span key={severity} className="flex items-center gap-1.5">
                  <span
                    className="h-1.5 w-1.5 rounded-full"
                    style={{ background: severityColor[severity] }}
                  />
                  <span className="mono text-[8px] uppercase tracking-[0.1em] text-faint">{severity}</span>
                </span>
              ))}
            </div>
            <div className="flex border border-white/10">
              <button
                type="button"
                onClick={() => setMode("3d")}
                className={cn(
                  "mono flex items-center gap-1.5 px-2.5 py-1.5 text-[9px] uppercase tracking-[0.1em] transition-colors",
                  mode === "3d" ? "bg-acid/10 text-acid" : "text-muted hover:text-white",
                )}
                aria-pressed={mode === "3d"}
              >
                <Box size={11} /> 3D
              </button>
              <button
                type="button"
                onClick={() => setMode("2d")}
                className={cn(
                  "mono flex items-center gap-1.5 border-l border-white/10 px-2.5 py-1.5 text-[9px] uppercase tracking-[0.1em] transition-colors",
                  mode === "2d" ? "bg-cyan/10 text-cyan" : "text-muted hover:text-white",
                )}
                aria-pressed={mode === "2d"}
              >
                <Grid2X2 size={11} /> 2D
              </button>
            </div>
          </div>
        </div>

        <div className="grid gap-4 p-4 xl:grid-cols-[1fr_300px]">
          <div>
            {mode === "3d" ? (
              <Suspense
                fallback={
                  <div className="skeleton flex h-[430px] items-center justify-center border border-white/[0.07]">
                    <span className="mono text-[10px] uppercase tracking-[0.14em] text-faint">
                      initializing WebGL topology…
                    </span>
                  </div>
                }
              >
                <ImpactGraph3D nodes={impact.graph.nodes} edges={impact.graph.edges} />
              </Suspense>
            ) : (
              <ImpactMap2D nodes={impact.graph.nodes} edges={impact.graph.edges} />
            )}
            <p className="mono mt-2 text-[9px] uppercase tracking-[0.1em] text-faint">
              {mode === "3d" ? "orbit enabled · hover a node for its label" : "static map · animated edge particles"}
            </p>
          </div>

          <div className="space-y-2">
            <p className="mono px-0.5 text-[9px] uppercase tracking-[0.14em] text-faint">
              Consumer exposure
            </p>
            {impact.consumers.length ? (
              impact.consumers.map((consumer) => (
                <div key={consumer.name} className="border border-white/[0.075] bg-black/20 p-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate text-[12px] font-medium text-white/90">{consumer.name}</p>
                      <p className="mono mt-0.5 text-[9px] uppercase tracking-[0.1em] text-faint">
                        {consumer.owner ?? "no owner declared"}
                      </p>
                    </div>
                    <SeverityBadge severity={consumer.severity} />
                  </div>
                  <div className="mt-2 flex items-center gap-3">
                    <span className="mono text-[9px] text-muted">
                      {consumer.affected_endpoints.length} affected
                    </span>
                    <span className="mono text-[9px] text-muted">
                      {consumer.finding_ids.length} findings
                    </span>
                  </div>
                  <div className="mt-2 space-y-1 border-t border-white/[0.06] pt-2">
                    {consumer.affected_endpoints.slice(0, 4).map((endpoint) => (
                      <p key={endpoint} className="mono truncate text-[9px] text-faint">
                        {endpoint}
                      </p>
                    ))}
                    {consumer.affected_endpoints.length > 4 ? (
                      <p className="mono text-[9px] text-faint">
                        +{consumer.affected_endpoints.length - 4} more
                      </p>
                    ) : null}
                  </div>
                </div>
              ))
            ) : (
              <div className="border border-white/[0.075] bg-black/20 px-3 py-6 text-center">
                <Users size={18} className="mx-auto text-faint" />
                <p className="mt-2 text-[11px] leading-relaxed text-faint">
                  No consumers declared. Add usage declarations before the next run to map exposure.
                </p>
              </div>
            )}

            {impact.unclaimed_endpoints.length ? (
              <div className="border border-medium/20 bg-medium/[0.035] p-3">
                <p className="mono text-[9px] uppercase tracking-[0.12em] text-medium">
                  Unclaimed affected endpoints · {impact.unclaimed_endpoints.length}
                </p>
                <p className="mt-1 text-[10px] leading-relaxed text-muted">
                  Changed, but no declared consumer claims them. Risk may be hidden in undeclared
                  clients.
                </p>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </section>
  );
}
