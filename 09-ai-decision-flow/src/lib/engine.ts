/** Pure graph helpers: no I/O, so the traversal rules are easy to test. */
import type { Branch, WorkflowGraph } from "./flow";

export const MAX_STEPS = 25; // guards against loops in a user-drawn graph

export type GraphNode = WorkflowGraph["nodes"][number];

export function validateGraph(graph: WorkflowGraph): string[] {
  const errors: string[] = [];
  const starts = graph.nodes.filter((n) => n.type === "start");
  if (starts.length !== 1) errors.push(`The flow needs exactly one Start node (found ${starts.length}).`);
  for (const n of graph.nodes) {
    if (n.type === "decision" && !n.data.prompt?.trim()) errors.push(`Decision "${n.data.label}" has an empty prompt.`);
  }
  const ids = new Set(graph.nodes.map((n) => n.id));
  for (const e of graph.edges) {
    if (!ids.has(e.source) || !ids.has(e.target)) errors.push(`Edge ${e.id} points at a node that no longer exists.`);
  }
  if (starts[0] && !graph.edges.some((e) => e.source === starts[0].id)) errors.push("The Start node is not connected.");
  return errors;
}

export function findStart(graph: WorkflowGraph): GraphNode | undefined {
  return graph.nodes.find((n) => n.type === "start");
}

export function getNode(graph: WorkflowGraph, id: string): GraphNode | undefined {
  return graph.nodes.find((n) => n.id === id);
}

/** Follow the edge leaving `fromId` on the chosen branch. */
export function nextNodeId(graph: WorkflowGraph, fromId: string, branch: Branch): string | null {
  const edge = graph.edges.find((e) => e.source === fromId && (e.data?.branch ?? e.sourceHandle ?? "next") === branch);
  return edge?.target ?? null;
}

export function edgeId(graph: WorkflowGraph, fromId: string, branch: Branch): string | null {
  return graph.edges.find((e) => e.source === fromId && (e.data?.branch ?? e.sourceHandle ?? "next") === branch)?.id ?? null;
}
