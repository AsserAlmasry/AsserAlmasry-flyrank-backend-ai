import { inngest } from "@/inngest/client";
import { validateGraph } from "@/lib/engine";
import type { WorkflowGraph } from "@/lib/flow";
import { providerLabel } from "@/lib/llm";
import { now, runs } from "@/lib/runs";

const MAX_INPUT = 4000;

/** Start a run: validate, record it, hand it to Inngest, answer 202 straight away. */
export async function POST(request: Request) {
  let body: { graph?: WorkflowGraph; input?: string };
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Body must be JSON: { graph, input }" }, { status: 400 });
  }
  const input = (body.input ?? "").trim();
  if (!input) return Response.json({ error: "input is required" }, { status: 400 });
  if (input.length > MAX_INPUT) return Response.json({ error: `input is longer than ${MAX_INPUT} characters` }, { status: 400 });
  if (!body.graph?.nodes || !body.graph?.edges) return Response.json({ error: "graph is required" }, { status: 400 });
  const problems = validateGraph(body.graph);
  if (problems.length) return Response.json({ error: "The workflow is not valid", problems }, { status: 400 });

  const run = runs.create({
    id: crypto.randomUUID().slice(0, 8),
    status: "queued",
    input,
    graph: body.graph,
    steps: [],
    activeNodeId: null,
    createdAt: now(),
    provider: providerLabel(),
  });
  try {
    await inngest.send({ name: "workflow/run.requested", data: { runId: run.id, graph: body.graph, input } });
  } catch (err) {
    runs.update(run.id, { status: "failed", error: `Could not reach Inngest: ${(err as Error).message}`, finishedAt: now() });
    return Response.json(
      { error: "Inngest is not reachable. Start the Dev Server: npx inngest-cli@latest dev", runId: run.id },
      { status: 503 },
    );
  }
  return Response.json({ runId: run.id, status: run.status }, { status: 202 });
}

/** Execution history: newest first, without the heavy fields. */
export async function GET() {
  return Response.json(
    runs.list().map(({ id, status, input, outcome, error, createdAt, finishedAt, steps, provider }) => ({
      id, status, input, outcome, error, createdAt, finishedAt, provider, steps: steps.length,
    })),
  );
}
