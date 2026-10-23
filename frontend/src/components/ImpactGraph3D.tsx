import { Html, Line, OrbitControls } from "@react-three/drei";
import { Canvas } from "@react-three/fiber";
import { DoubleSide } from "three";
import { useMemo, useState } from "react";
import type { GraphEdge, GraphNode } from "../types";

const severityColor: Record<string, string> = {
  critical: "#ff5470",
  high: "#ff8a45",
  medium: "#f4c95d",
  low: "#6ca8ff",
  info: "#8b98a9",
};

interface Positioned {
  node: GraphNode;
  position: [number, number, number];
}

function useNodePositions(nodes: GraphNode[]): Map<string, Positioned> {
  return useMemo(() => {
    const consumers = nodes.filter((node) => node.kind === "consumer");
    const endpoints = nodes.filter((node) => node.kind === "endpoint");
    const positions = new Map<string, Positioned>();
    consumers.forEach((node, index) => {
      const angle = (index / Math.max(consumers.length, 1)) * Math.PI * 2 + Math.PI / 6;
      positions.set(node.id, {
        node,
        position: [Math.cos(angle) * 6.2, 0.4, Math.sin(angle) * 6.2],
      });
    });
    endpoints.forEach((node, index) => {
      const angle = (index / Math.max(endpoints.length, 1)) * Math.PI * 2 - Math.PI / 2;
      const radius = index % 2 === 0 ? 2.7 : 3.4;
      positions.set(node.id, {
        node,
        position: [Math.cos(angle) * radius, 1.4 + (index % 3) * 0.32, Math.sin(angle) * radius],
      });
    });
    return positions;
  }, [nodes]);
}

function EdgeLine({
  edge,
  positions,
}: {
  edge: GraphEdge;
  positions: Map<string, Positioned>;
}) {
  const from = positions.get(edge.source)?.position;
  const to = positions.get(edge.target)?.position;
  if (!from || !to) return null;
  const mid: [number, number, number] = [
    (from[0] + to[0]) / 2,
    Math.max(from[1], to[1]) + 0.35,
    (from[2] + to[2]) / 2,
  ];
  return (
    <Line
      points={[from, mid, to]}
      color="#3a5560"
      lineWidth={0.8}
      transparent
      opacity={0.45}
      dashed
      dashSize={0.16}
      gapSize={0.1}
    />
  );
}

function GraphNodeMesh({
  entry,
  hovered,
  onHover,
}: {
  entry: Positioned;
  hovered: string | null;
  onHover: (id: string | null) => void;
}) {
  const { node, position } = entry;
  const isConsumer = node.kind === "consumer";
  const color = isConsumer ? "#5ce1e6" : (severityColor[node.severity ?? "info"] ?? "#8b98a9");
  const isHovered = hovered === node.id;

  return (
    <group position={position}>
      <mesh
        onPointerOver={(event) => {
          event.stopPropagation();
          onHover(node.id);
          document.body.style.cursor = "pointer";
        }}
        onPointerOut={() => {
          onHover(null);
          document.body.style.cursor = "auto";
        }}
        scale={isHovered ? 1.28 : 1}
      >
        {isConsumer ? <octahedronGeometry args={[0.46, 0]} /> : <icosahedronGeometry args={[0.25, 0]} />}
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={isHovered ? 1.1 : 0.4}
          metalness={0.2}
          roughness={0.35}
        />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.35, 0]}>
        <ringGeometry args={[0.55, 0.59, 32]} />
        <meshBasicMaterial color={color} transparent opacity={0.35} side={DoubleSide} />
      </mesh>
      {(isConsumer || isHovered) && (
        <Html center distanceFactor={11} position={[0, isConsumer ? 0.9 : 0.65, 0]} zIndexRange={[20, 0]}>
          <div
            className="pointer-events-none whitespace-nowrap border px-1.5 py-0.5 font-mono text-[8px] uppercase tracking-wider"
            style={{
              borderColor: `${color}66`,
              background: "rgba(6,9,12,0.88)",
              color: isConsumer ? "#d7f9fb" : "#dbe3e8",
            }}
          >
            {node.label}
          </div>
        </Html>
      )}
    </group>
  );
}

function Scene({ nodes, edges }: { nodes: GraphNode[]; edges: GraphEdge[] }) {
  const positions = useNodePositions(nodes);
  const [hovered, setHovered] = useState<string | null>(null);

  return (
    <>
      <color attach="background" args={["#070b0e"]} />
      <fog attach="fog" args={["#070b0e", 13, 22]} />
      <ambientLight intensity={0.7} />
      <pointLight position={[6, 8, 6]} intensity={38} color="#c8f45a" />
      <pointLight position={[-7, 4, -6]} intensity={22} color="#5ce1e6" />
      <gridHelper args={[22, 22, "#1d2b33", "#111a20"]} position={[0, -0.9, 0]} />
      {edges.map((edge, index) => (
        <EdgeLine key={`${edge.source}-${edge.target}-${index}`} edge={edge} positions={positions} />
      ))}
      {Array.from(positions.values()).map((entry) => (
        <GraphNodeMesh
          key={entry.node.id}
          entry={entry}
          hovered={hovered}
          onHover={setHovered}
        />
      ))}
      <OrbitControls
        enablePan={false}
        enableZoom
        minDistance={8}
        maxDistance={18}
        autoRotate
        autoRotateSpeed={0.45}
        maxPolarAngle={Math.PI / 2.05}
      />
    </>
  );
}

export default function ImpactGraph3D({
  nodes,
  edges,
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
}) {
  if (!nodes.length) {
    return (
      <div className="flex h-[430px] items-center justify-center border border-white/[0.07] bg-black/25">
        <p className="text-sm text-faint">No topology to render for this contract pair.</p>
      </div>
    );
  }

  return (
    <div className="graph-canvas relative h-[430px] w-full overflow-hidden border border-white/[0.07] bg-[#070b0e]">
      <Canvas
        dpr={[1, 1.8]}
        camera={{ position: [0, 7.4, 11.5], fov: 40 }}
        gl={{ antialias: true, alpha: false }}
        onCreated={({ gl }) => gl.setClearColor("#070b0e")}
      >
        <Scene nodes={nodes} edges={edges} />
      </Canvas>
      <div className="pointer-events-none absolute bottom-3 left-3 flex items-center gap-3">
        <span className="mono text-[8px] uppercase tracking-[0.16em] text-faint">
          drag to orbit · scroll to zoom
        </span>
      </div>
      <div className="pointer-events-none absolute right-3 top-3 border border-white/10 bg-black/40 px-2 py-1">
        <span className="mono text-[8px] uppercase tracking-[0.14em] text-faint">R3F / WEBGL</span>
      </div>
    </div>
  );
}
