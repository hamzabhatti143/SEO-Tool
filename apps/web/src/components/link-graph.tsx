"use client";

import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  MarkerType,
  type Edge,
  type Node,
} from "reactflow";
import "reactflow/dist/style.css";

import type { GraphEdge, GraphNode } from "@/lib/api";

function truncate(s: string, n: number) {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

/** Internal-link graph laid out on a circle; orphan pages are highlighted. */
export default function LinkGraph({
  nodes,
  edges,
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
}) {
  const n = Math.max(nodes.length, 1);
  const radius = Math.max(220, n * 26);

  const rfNodes: Node[] = nodes.map((node, i) => {
    const angle = (2 * Math.PI * i) / n;
    return {
      id: node.id,
      position: {
        x: radius + radius * Math.cos(angle),
        y: radius + radius * Math.sin(angle),
      },
      data: {
        label: `${truncate(node.label, 22)}${
          node.is_orphan ? " ⚠" : ""
        }`,
      },
      style: {
        fontSize: 11,
        width: 150,
        padding: 6,
        borderRadius: 6,
        border: node.is_orphan ? "2px solid #dc2626" : "1px solid #94a3b8",
        background: node.is_orphan ? "#fee2e2" : "#ffffff",
      },
    };
  });

  const rfEdges: Edge[] = edges.map((e, i) => ({
    id: `e-${i}`,
    source: e.source,
    target: e.target,
    markerEnd: { type: MarkerType.ArrowClosed },
    style: { stroke: "#cbd5e1" },
  }));

  return (
    <div style={{ height: 520 }} className="rounded-md border">
      <ReactFlow nodes={rfNodes} edges={rfEdges} fitView minZoom={0.1}>
        <Background />
        <Controls />
        <MiniMap
          nodeColor={(node) =>
            (node.style?.background as string) ?? "#ffffff"
          }
          zoomable
          pannable
        />
      </ReactFlow>
    </div>
  );
}
