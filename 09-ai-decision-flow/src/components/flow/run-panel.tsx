"use client";

import { AlertTriangle, CheckCircle2, History, ListTree, Loader2, Play, RotateCcw, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

export type StepView = {
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

export type RunView = {
  id: string;
  status: "queued" | "running" | "completed" | "failed";
  input: string;
  steps: StepView[];
  activeNodeId: string | null;
  outcome?: string;
  error?: string;
  createdAt: string;
  finishedAt?: string;
  provider: string;
};

export type HistoryItem = Pick<RunView, "id" | "status" | "input" | "outcome" | "error" | "createdAt"> & { steps: number };

const STATUS_STYLE: Record<RunView["status"], string> = {
  queued: "bg-slate-100 text-slate-700",
  running: "bg-amber-100 text-amber-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};

const time = (iso?: string) => (iso ? new Date(iso).toLocaleTimeString([], { hour12: false }) : "");

export function RunPanel(props: {
  input: string;
  onInput: (v: string) => void;
  onRun: () => void;
  busy: boolean;
  run: RunView | null;
  problems: string[];
  history: HistoryItem[];
  onPickHistory: (id: string) => void;
  onRerun: (input: string) => void;
}) {
  const { run } = props;
  return (
    <aside className="flex w-[380px] shrink-0 flex-col border-l bg-muted/20">
      <section className="space-y-2 border-b p-4">
        <h2 className="text-sm font-semibold">Run the workflow</h2>
        <Textarea
          value={props.input}
          onChange={(e) => props.onInput(e.target.value)}
          placeholder="Paste the text to route, e.g. a customer email…"
          className="min-h-20 bg-background text-sm"
        />
        <div className="flex gap-2">
          <Button onClick={props.onRun} disabled={props.busy || !props.input.trim()} className="flex-1">
            {props.busy ? <Loader2 className="animate-spin" /> : <Play />} {props.busy ? "Running…" : "Run"}
          </Button>
          {run && !props.busy && (
            <Button variant="outline" onClick={() => props.onRerun(run.input)} title="Run this input again">
              <RotateCcw /> Again
            </Button>
          )}
        </div>
        {props.problems.length > 0 && (
          <div className="rounded-md border border-red-200 bg-red-50 p-2 text-xs text-red-800">
            <div className="mb-1 flex items-center gap-1 font-semibold"><AlertTriangle className="size-3.5" /> Can&apos;t run yet</div>
            <ul className="list-disc pl-4">{props.problems.map((p) => <li key={p}>{p}</li>)}</ul>
          </div>
        )}
      </section>

      <section className="flex min-h-0 flex-1 flex-col border-b">
        <div className="flex items-center justify-between px-4 pt-3 pb-2">
          <h2 className="flex items-center gap-1.5 text-sm font-semibold"><ListTree className="size-4" /> Execution log</h2>
          {run && <Badge className={cn("border-0", STATUS_STYLE[run.status])}>{run.status}</Badge>}
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-3 text-xs">
          {!run && <p className="text-muted-foreground">Run the workflow to see each node&apos;s decision here, in order.</p>}
          {run && (
            <>
              <p className="mb-2 text-muted-foreground">
                Run <span className="font-mono">{run.id}</span> · {run.provider}
              </p>
              <ol className="space-y-1.5">
                {run.steps.map((s) => (
                  <li key={s.index} className="rounded-md border bg-background p-2">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium">
                        <span className="mr-1 text-muted-foreground">{s.index + 1}.</span>
                        {s.kind === "start" ? "Start: " : s.kind === "end" ? "Outcome: " : ""}
                        {s.label}
                      </span>
                      {s.answer === "YES" && <Badge className="border-0 bg-green-600 text-white">YES</Badge>}
                      {s.answer === "NO" && <Badge className="border-0 bg-red-600 text-white">NO</Badge>}
                      {!s.answer && !s.finishedAt && !s.error && <Loader2 className="size-3.5 animate-spin text-amber-600" />}
                      {s.kind === "end" && <CheckCircle2 className="size-4 text-sky-700" />}
                    </div>
                    {s.prompt && <p className="mt-1 text-muted-foreground">{s.prompt}</p>}
                    <p className="mt-1 text-[10px] text-muted-foreground">
                      {time(s.startedAt)}
                      {s.durationMs !== undefined && ` · ${s.durationMs} ms`}
                      {s.attempts && s.attempts > 1 ? ` · attempt ${s.attempts}` : ""}
                    </p>
                    {s.error && (
                      <p className="mt-1 flex items-start gap-1 text-red-700"><XCircle className="mt-0.5 size-3 shrink-0" /> {s.error}</p>
                    )}
                  </li>
                ))}
              </ol>
              {run.outcome && <p className="mt-2 rounded-md bg-sky-50 p-2 font-medium text-sky-900">Result: {run.outcome}</p>}
              {run.error && <p className="mt-2 rounded-md bg-red-50 p-2 text-red-800">Failed: {run.error}</p>}
            </>
          )}
        </div>
      </section>

      <section className="max-h-56 overflow-y-auto p-4 text-xs">
        <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold"><History className="size-4" /> History</h2>
        {props.history.length === 0 && <p className="text-muted-foreground">No runs yet.</p>}
        <ul className="space-y-1">
          {props.history.map((h) => (
            <li key={h.id}>
              <button
                onClick={() => props.onPickHistory(h.id)}
                className={cn("w-full rounded-md border bg-background px-2 py-1.5 text-left hover:bg-muted",
                  run?.id === h.id && "border-primary")}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate">{h.input}</span>
                  <Badge className={cn("shrink-0 border-0", STATUS_STYLE[h.status])}>{h.status}</Badge>
                </div>
                <div className="mt-0.5 truncate text-[10px] text-muted-foreground">
                  {time(h.createdAt)} · {h.outcome ?? h.error ?? "…"}
                </div>
              </button>
            </li>
          ))}
        </ul>
      </section>
    </aside>
  );
}
