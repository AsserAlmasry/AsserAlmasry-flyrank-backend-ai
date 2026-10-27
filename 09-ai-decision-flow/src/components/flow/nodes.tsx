"use client";

import { Handle, Position, useReactFlow, type NodeProps } from "@xyflow/react";
import { CircleCheck, CircleHelp, CircleX, Flag, Loader2, Play } from "lucide-react";
import { BRANCH_COLORS, type DecisionNode, type EndNode, type RunVisual, type StartNode } from "@/lib/flow";
import { cn } from "@/lib/utils";

const RING: Record<RunVisual, string> = {
  idle: "border-border",
  active: "border-amber-500 ring-4 ring-amber-300/60 shadow-amber-200",
  yes: "border-green-600 ring-2 ring-green-300/70",
  no: "border-red-600 ring-2 ring-red-300/70",
  done: "border-sky-600 ring-4 ring-sky-300/60",
  error: "border-red-700 ring-4 ring-red-400/70",
};

function Shell(props: { state?: RunVisual; selected?: boolean; className?: string; children: React.ReactNode }) {
  return (
    <div
      className={cn(
        "rounded-xl border-2 bg-card text-card-foreground shadow-sm transition-all duration-300",
        RING[props.state ?? "idle"],
        props.selected && (props.state ?? "idle") === "idle" && "border-primary",
        props.className,
      )}
    >
      {props.children}
    </div>
  );
}

function LabelInput({ id, value }: { id: string; value: string }) {
  const { updateNodeData } = useReactFlow();
  return (
    <input
      aria-label="Node label"
      className="nodrag w-full bg-transparent text-sm font-semibold outline-none focus:underline"
      value={value}
      onChange={(e) => updateNodeData(id, { label: e.target.value })}
    />
  );
}

export function StartNodeView({ id, data, selected }: NodeProps<StartNode>) {
  return (
    <Shell state={data.runState} selected={selected} className="w-52">
      <div className="flex items-center gap-2 rounded-t-[10px] bg-slate-900 px-3 py-1.5 text-[11px] font-medium uppercase tracking-wide text-white">
        <Play className="size-3" /> Start
      </div>
      <div className="px-3 py-2">
        <LabelInput id={id} value={data.label} />
        <p className="mt-1 text-[11px] text-muted-foreground">The run&apos;s input text enters here.</p>
      </div>
      <Handle type="source" position={Position.Right} id="next" className="!size-3 !bg-slate-500" />
    </Shell>
  );
}

export function DecisionNodeView({ id, data, selected }: NodeProps<DecisionNode>) {
  const { updateNodeData } = useReactFlow();
  const state = data.runState ?? "idle";
  return (
    <Shell state={state} selected={selected} className="w-64">
      <Handle type="target" position={Position.Left} className="!size-3 !bg-slate-500" />
      <div className="flex items-center justify-between gap-2 rounded-t-[10px] bg-violet-600 px-3 py-1.5 text-[11px] font-medium uppercase tracking-wide text-white">
        <span className="flex items-center gap-1.5">
          <CircleHelp className="size-3" /> AI decision
        </span>
        {state === "active" && <Loader2 className="size-3 animate-spin" />}
        {data.answer === "YES" && <span className="flex items-center gap-1 rounded bg-green-600 px-1.5"><CircleCheck className="size-3" />YES</span>}
        {data.answer === "NO" && <span className="flex items-center gap-1 rounded bg-red-600 px-1.5"><CircleX className="size-3" />NO</span>}
      </div>
      <div className="space-y-1.5 px-3 py-2">
        <LabelInput id={id} value={data.label} />
        <textarea
          aria-label="Decision prompt"
          className="nodrag nowheel min-h-16 w-full resize-y rounded-md border bg-muted/40 px-2 py-1 text-xs leading-snug outline-none focus:border-violet-500"
          placeholder="Ask a yes/no question about the input…"
          value={data.prompt}
          onChange={(e) => updateNodeData(id, { prompt: e.target.value })}
        />
      </div>
      <div className="flex justify-end gap-3 px-3 pb-2 text-[10px] font-bold">
        <span style={{ color: BRANCH_COLORS.yes }}>YES ▸</span>
        <span style={{ color: BRANCH_COLORS.no }}>NO ▸</span>
      </div>
      <Handle type="source" position={Position.Right} id="yes" style={{ top: "38%", background: BRANCH_COLORS.yes }} className="!size-3.5" />
      <Handle type="source" position={Position.Right} id="no" style={{ top: "72%", background: BRANCH_COLORS.no }} className="!size-3.5" />
    </Shell>
  );
}

export function EndNodeView({ id, data, selected }: NodeProps<EndNode>) {
  return (
    <Shell state={data.runState} selected={selected} className="w-48">
      <Handle type="target" position={Position.Left} className="!size-3 !bg-slate-500" />
      <div className="flex items-center gap-2 rounded-t-[10px] bg-sky-700 px-3 py-1.5 text-[11px] font-medium uppercase tracking-wide text-white">
        <Flag className="size-3" /> Outcome
      </div>
      <div className="px-3 py-2">
        <LabelInput id={id} value={data.label} />
      </div>
    </Shell>
  );
}

export const nodeTypes = { start: StartNodeView, decision: DecisionNodeView, end: EndNodeView };
