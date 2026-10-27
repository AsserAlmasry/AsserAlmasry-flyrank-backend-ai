import { runs } from "@/lib/runs";

export async function GET(_request: Request, ctx: RouteContext<"/api/runs/[id]">) {
  const { id } = await ctx.params;
  const run = runs.get(id);
  if (!run) return Response.json({ error: `Run ${id} not found` }, { status: 404 });
  const { graph: _graph, ...rest } = run; // the client already has the graph
  return Response.json(rest);
}
