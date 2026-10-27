/**
 * In-memory run store. The Next.js server process both serves the API and runs the Inngest functions
 * (Inngest calls /api/inngest), so a module-level Map on globalThis is shared by both.
 * Like every in-memory store: it's gone on restart. A database would replace this in production.
 */
import type { WorkflowGraph } from "./flow";

export type StepRecord = {
  index: number;
  nodeId: string;
  kind: "start" | "decision" | "end";
  label: string;
  prompt?: string;
  answer?: "YES" | "NO";
  edgeId?: string | null;
  attempts?: number;
  error?: string;
  startedAt: string;
  finishedAt?: string;
  durationMs?: number;
};

export type RunRecord = {
  id: string;
  status: "queued" | "running" | "completed" | "failed";
  input: string;
  graph: WorkflowGraph;
  steps: StepRecord[];
  activeNodeId: string | null;
  outcome?: string;
  error?: string;
  createdAt: string;
  finishedAt?: string;
  provider: string;
};

const g = globalThis as unknown as { __runs?: Map<string, RunRecord> };
const store: Map<string, RunRecord> = (g.__runs ??= new Map<string, RunRecord>());

export const runs = {
  create(run: RunRecord) {
    store.set(run.id, run);
    return run;
  },
  get(id: string) {
    return store.get(id);
  },
  list() {
    return [...store.values()].sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  },
  update(id: string, patch: Partial<RunRecord>) {
    const run = store.get(id);
    if (run) Object.assign(run, patch);
    return run;
  },
  /** Upsert by index: Inngest replays the function body, so writes must be idempotent. */
  putStep(id: string, step: StepRecord) {
    const run = store.get(id);
    if (!run) return;
    const at = run.steps.findIndex((s) => s.index === step.index);
    if (at === -1) run.steps.push(step);
    else run.steps[at] = { ...run.steps[at], ...step };
    run.steps.sort((a, b) => a.index - b.index);
  },
};

export const now = () => new Date().toISOString();
