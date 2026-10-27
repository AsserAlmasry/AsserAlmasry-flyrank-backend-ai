import type { Edge, Node } from "@xyflow/react";

/** Visual state of a node while a workflow runs. */
export type RunVisual = "idle" | "active" | "yes" | "no" | "done" | "error";

export type StartData = { label: string; runState?: RunVisual };
export type DecisionData = { label: string; prompt: string; runState?: RunVisual; answer?: "YES" | "NO" };
export type EndData = { label: string; runState?: RunVisual };

export type StartNode = Node<StartData, "start">;
export type DecisionNode = Node<DecisionData, "decision">;
export type EndNode = Node<EndData, "end">;
export type FlowNode = StartNode | DecisionNode | EndNode;

/** "yes" / "no" leave a decision node; "next" leaves the start node. */
export type Branch = "yes" | "no" | "next";
export type FlowEdge = Edge<{ branch: Branch }>;

/** The plain JSON the server receives and the user can export / import. */
export type WorkflowGraph = {
  nodes: { id: string; type: FlowNode["type"]; position: { x: number; y: number }; data: { label: string; prompt?: string } }[];
  edges: { id: string; source: string; target: string; sourceHandle?: string | null; data: { branch: Branch } }[];
};

export const BRANCH_COLORS: Record<Branch, string> = { yes: "#16a34a", no: "#dc2626", next: "#64748b" };

export function edgeStyle(branch: Branch, active = false): Partial<FlowEdge> {
  return {
    type: "smoothstep",
    label: branch === "next" ? undefined : branch.toUpperCase(),
    animated: active,
    style: { stroke: BRANCH_COLORS[branch], strokeWidth: active ? 3 : 2, opacity: active ? 1 : 0.85 },
    labelStyle: { fill: BRANCH_COLORS[branch], fontWeight: 700, fontSize: 11 },
    labelBgStyle: { fill: "white" },
    labelBgPadding: [4, 2],
    labelBgBorderRadius: 4,
  };
}

/** Strip runtime-only fields so what we save / send is just the graph. */
export function toGraph(nodes: FlowNode[], edges: FlowEdge[]): WorkflowGraph {
  return {
    nodes: nodes.map((n) => ({
      id: n.id,
      type: n.type,
      position: { x: Math.round(n.position.x), y: Math.round(n.position.y) },
      data: n.type === "decision" ? { label: n.data.label, prompt: n.data.prompt } : { label: n.data.label },
    })),
    edges: edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      sourceHandle: e.sourceHandle ?? null,
      data: { branch: e.data?.branch ?? "next" },
    })),
  };
}

export function fromGraph(graph: WorkflowGraph): { nodes: FlowNode[]; edges: FlowEdge[] } {
  return {
    nodes: graph.nodes.map((n) => ({ ...n, data: { ...n.data, prompt: n.data.prompt ?? "" } }) as FlowNode),
    edges: graph.edges.map((e) => ({ ...e, ...edgeStyle(e.data.branch) }) as FlowEdge),
  };
}

export const EXAMPLE_GRAPH: WorkflowGraph = {
  nodes: [
    { id: "start", type: "start", position: { x: 0, y: 160 }, data: { label: "Incoming message" } },
    { id: "is-support", type: "decision", position: { x: 260, y: 130 }, data: { label: "Support?", prompt: "Is this a support request (the sender has a problem with something they already use)?" } },
    { id: "is-urgent", type: "decision", position: { x: 600, y: 0 }, data: { label: "Urgent?", prompt: "Is the problem urgent (something is down, broken for many people, or blocking work right now)?" } },
    { id: "is-sales", type: "decision", position: { x: 600, y: 300 }, data: { label: "Sales lead?", prompt: "Is the sender asking about pricing, plans, a demo or buying?" } },
    { id: "escalate", type: "end", position: { x: 960, y: -40 }, data: { label: "Escalate to on-call" } },
    { id: "support-queue", type: "end", position: { x: 960, y: 90 }, data: { label: "Support queue" } },
    { id: "sales", type: "end", position: { x: 960, y: 260 }, data: { label: "Sales team" } },
    { id: "inbox", type: "end", position: { x: 960, y: 380 }, data: { label: "General inbox" } },
  ],
  edges: [
    { id: "e-start", source: "start", target: "is-support", sourceHandle: "next", data: { branch: "next" } },
    { id: "e-support-yes", source: "is-support", target: "is-urgent", sourceHandle: "yes", data: { branch: "yes" } },
    { id: "e-support-no", source: "is-support", target: "is-sales", sourceHandle: "no", data: { branch: "no" } },
    { id: "e-urgent-yes", source: "is-urgent", target: "escalate", sourceHandle: "yes", data: { branch: "yes" } },
    { id: "e-urgent-no", source: "is-urgent", target: "support-queue", sourceHandle: "no", data: { branch: "no" } },
    { id: "e-sales-yes", source: "is-sales", target: "sales", sourceHandle: "yes", data: { branch: "yes" } },
    { id: "e-sales-no", source: "is-sales", target: "inbox", sourceHandle: "no", data: { branch: "no" } },
  ],
};
