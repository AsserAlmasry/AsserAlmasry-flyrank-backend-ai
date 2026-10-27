import { edgeId, findStart, getNode, MAX_STEPS, nextNodeId } from "@/lib/engine";
import type { Branch, WorkflowGraph } from "@/lib/flow";
import { askYesNo } from "@/lib/llm";
import { now, runs } from "@/lib/runs";
import { inngest } from "./client";

type RunRequested = { runId: string; graph: WorkflowGraph; input: string };

/**
 * Executes one workflow run. Every decision node is its own Inngest step, so:
 *  - a node that fails (LLM error, answer that isn't YES/NO) is retried on its own,
 *  - nodes that already finished are never re-run on a retry (their answers are memoised by Inngest),
 *  - the dashboard shows one row per node, in execution order.
 */
export const runWorkflow = inngest.createFunction(
  {
    id: "run-workflow",
    triggers: [{ event: "workflow/run.requested" }],
    retries: 2, // per step: 1 try + 2 retries
    onFailure: async ({ event, error }) => {
      const { runId } = (event.data.event.data ?? {}) as RunRequested;
      const run = runs.get(runId);
      if (!run) return;
      const failing = run.steps.find((s) => !s.finishedAt);
      if (failing) runs.putStep(runId, { ...failing, error: error.message, finishedAt: now() });
      runs.update(runId, { status: "failed", error: error.message, finishedAt: now() });
    },
  },
  async ({ event, step, attempt }) => {
    const { runId, graph, input } = event.data as RunRequested;
    runs.update(runId, { status: "running" });

    let current = findStart(graph);
    let incomingEdge: string | null = null;
    for (let index = 0; current && index < MAX_STEPS; index++) {
      const node = current;
      if (node.type === "decision") {
        const prompt = node.data.prompt ?? "";
        // One Inngest step per node. The step id includes the index so a node visited twice gets two steps.
        const answer = await step.run(`node-${index}-${node.id}`, async () => {
          const started = Date.now();
          runs.update(runId, { activeNodeId: node.id });
          runs.putStep(runId, { index, nodeId: node.id, kind: "decision", label: node.data.label, prompt,
            edgeId: incomingEdge, attempts: attempt + 1, startedAt: now() });
          try {
            const { answer } = await askYesNo(prompt, input);
            runs.putStep(runId, { index, nodeId: node.id, kind: "decision", label: node.data.label, answer,
              error: undefined, finishedAt: now(), durationMs: Date.now() - started, startedAt: new Date(started).toISOString() });
            return answer;
          } catch (err) {
            runs.putStep(runId, { index, nodeId: node.id, kind: "decision", label: node.data.label,
              error: `attempt ${attempt + 1}: ${(err as Error).message}`, startedAt: new Date(started).toISOString() });
            throw err; // Inngest retries this step (and only this step)
          }
        });
        const branch: Branch = answer === "YES" ? "yes" : "no";
        incomingEdge = edgeId(graph, node.id, branch);
        const nextId = nextNodeId(graph, node.id, branch);
        if (!nextId) {
          runs.update(runId, { status: "completed", activeNodeId: null, finishedAt: now(),
            outcome: `Stopped: "${node.data.label}" has no ${answer} edge` });
          return { runId, outcome: null, stoppedAt: node.id };
        }
        current = getNode(graph, nextId);
      } else if (node.type === "start") {
        runs.putStep(runId, { index, nodeId: node.id, kind: "start", label: node.data.label, startedAt: now(), finishedAt: now(), durationMs: 0 });
        incomingEdge = edgeId(graph, node.id, "next");
        const nextId = nextNodeId(graph, node.id, "next");
        current = nextId ? getNode(graph, nextId) : undefined;
      } else {
        // An outcome node: the run is finished.
        runs.putStep(runId, { index, nodeId: node.id, kind: "end", label: node.data.label, edgeId: incomingEdge,
          startedAt: now(), finishedAt: now(), durationMs: 0 });
        runs.update(runId, { status: "completed", activeNodeId: null, outcome: node.data.label, finishedAt: now() });
        return { runId, outcome: node.data.label };
      }
    }
    const reason = current ? `Stopped after ${MAX_STEPS} steps (is there a loop?)` : "Reached a node with no outgoing edge";
    runs.update(runId, { status: "completed", activeNodeId: null, outcome: reason, finishedAt: now() });
    return { runId, outcome: null, reason };
  },
);

export const functions = [runWorkflow];
