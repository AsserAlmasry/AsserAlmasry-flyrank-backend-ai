"use client";

import "@xyflow/react/dist/style.css";

import {
  addEdge,
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  type Connection,
} from "@xyflow/react";
import { CircleHelp, Download, Flag, FolderOpen, RotateCcw, Save, Upload } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { nodeTypes } from "@/components/flow/nodes";
import { RunPanel, type HistoryItem, type RunView } from "@/components/flow/run-panel";
import {
  edgeStyle,
  EXAMPLE_GRAPH,
  fromGraph,
  toGraph,
  type Branch,
  type FlowEdge,
  type FlowNode,
  type RunVisual,
  type WorkflowGraph,
} from "@/lib/flow";

const AUTOSAVE_KEY = "ai-decision-flow:current";
const SAVED_KEY = "ai-decision-flow:saved";
const POLL_MS = 600;

// localStorage can be missing or throw (private mode, blocked storage): never let that break the editor.
function readStore<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}
function writeStore(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage full or blocked: keep working, just don't persist */
  }
}

function isGraph(x: unknown): x is WorkflowGraph {
  const g = x as WorkflowGraph;
  return !!g && Array.isArray(g.nodes) && Array.isArray(g.edges) && g.nodes.every((n) => n.id && n.type && n.position && n.data);
}

function Editor() {
  // This component only renders in the browser (see flow-client.tsx), so localStorage can be read directly.
  const [initial] = useState(() => fromGraph(readStore<WorkflowGraph>(AUTOSAVE_KEY, EXAMPLE_GRAPH)));
  const [nodes, setNodes, onNodesChange] = useNodesState<FlowNode>(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState<FlowEdge>(initial.edges);
  const [saved, setSaved] = useState<Record<string, WorkflowGraph>>(() => readStore(SAVED_KEY, {}));
  const [input, setInput] = useState("Help! Our dashboard has been down for everyone since 9am and we can't log in.");
  const [run, setRun] = useState<RunView | null>(null);
  const [busy, setBusy] = useState(false);
  const [problems, setProblems] = useState<string[]>([]);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const loadGraph = useCallback(
    (g: WorkflowGraph) => {
      const f = fromGraph(g);
      setNodes(f.nodes);
      setEdges(f.edges);
      setRun(null);
    },
    [setNodes, setEdges],
  );

  // Load the run history once (async: the state update happens in a callback, after the fetch).
  useEffect(() => {
    fetch("/api/runs").then((r) => r.json()).then(setHistory).catch(() => {});
  }, []);

  // Autosave the graph locally on every edit.
  useEffect(() => {
    writeStore(AUTOSAVE_KEY, toGraph(nodes, edges));
  }, [nodes, edges]);

  const flash = (msg: string) => {
    setNotice(msg);
    setTimeout(() => setNotice(null), 2500);
  };

  // ------------------------------------------------------------------ editing
  const onConnect = useCallback(
    (c: Connection) => {
      const branch: Branch = c.sourceHandle === "yes" || c.sourceHandle === "no" ? c.sourceHandle : "next";
      setEdges((eds) =>
        addEdge(
          { ...c, id: `e-${c.source}-${branch}-${c.target}`, data: { branch }, ...edgeStyle(branch) } as FlowEdge,
          // One edge per branch: connecting YES again replaces the old YES edge.
          eds.filter((e) => !(e.source === c.source && (e.sourceHandle ?? "next") === (c.sourceHandle ?? "next"))),
        ),
      );
    },
    [setEdges],
  );

  const addNode = (type: "decision" | "end") => {
    const id = `${type}-${crypto.randomUUID().slice(0, 6)}`;
    const y = 60 + (nodes.length % 6) * 80;
    const node =
      type === "decision"
        ? { id, type, position: { x: 420, y }, data: { label: "New question", prompt: "" } }
        : { id, type, position: { x: 900, y }, data: { label: "New outcome" } };
    setNodes((ns) => [...ns, node as FlowNode]);
  };

  // ------------------------------------------------------------------ save / load / export / import
  const saveAs = () => {
    const name = window.prompt("Save this workflow as:", "My workflow")?.trim();
    if (!name) return;
    const next = { ...saved, [name]: toGraph(nodes, edges) };
    setSaved(next);
    writeStore(SAVED_KEY, next);
    flash(`Saved "${name}"`);
  };

  const exportJson = () => {
    const blob = new Blob([JSON.stringify(toGraph(nodes, edges), null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "workflow.json";
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const importJson = async (file: File | undefined) => {
    if (!file) return;
    try {
      const parsed = JSON.parse(await file.text());
      if (!isGraph(parsed)) throw new Error("not a workflow file");
      loadGraph(parsed);
      flash(`Imported ${file.name}`);
    } catch (err) {
      flash(`Import failed: ${(err as Error).message}`);
    }
  };

  // ------------------------------------------------------------------ running
  const poll = useCallback(async (runId: string) => {
    for (;;) {
      const res = await fetch(`/api/runs/${runId}`);
      if (!res.ok) break;
      const r: RunView = await res.json();
      setRun(r);
      if (r.status === "completed" || r.status === "failed") break;
      await new Promise((ok) => setTimeout(ok, POLL_MS));
    }
    setBusy(false);
    fetch("/api/runs").then((r) => r.json()).then(setHistory).catch(() => {});
  }, []);

  const start = async (text: string) => {
    setBusy(true);
    setProblems([]);
    setRun(null);
    try {
      const res = await fetch("/api/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ graph: toGraph(nodes, edges), input: text }),
      });
      const body = await res.json();
      if (res.status !== 202) {
        setProblems(body.problems ?? [body.error ?? `HTTP ${res.status}`]);
        setBusy(false);
        return;
      }
      await poll(body.runId);
    } catch (err) {
      setProblems([`Network error: ${(err as Error).message}`]);
      setBusy(false);
    }
  };

  const pickHistory = async (id: string) => {
    const res = await fetch(`/api/runs/${id}`);
    if (res.ok) setRun(await res.json());
  };

  // ------------------------------------------------------------------ visual execution state
  const { viewNodes, viewEdges } = useMemo(() => {
    const visual = new Map<string, { runState: RunVisual; answer?: "YES" | "NO" }>();
    const pathEdges = new Set<string>();
    let activeEdge: string | null = null;
    for (const s of run?.steps ?? []) {
      if (s.edgeId) pathEdges.add(s.edgeId);
      if (s.kind === "decision") {
        const state: RunVisual = s.answer ? (s.answer === "YES" ? "yes" : "no") : s.error && s.finishedAt ? "error" : "active";
        visual.set(s.nodeId, { runState: state, answer: s.answer });
        if (state === "active") activeEdge = s.edgeId ?? null;
      } else {
        visual.set(s.nodeId, { runState: "done" });
      }
    }
    if (run?.status === "failed") {
      const last = run.steps.at(-1);
      if (last && !last.answer) visual.set(last.nodeId, { runState: "error" });
    }
    const viewNodes = nodes.map((n) => {
      const v = visual.get(n.id);
      return { ...n, data: { ...n.data, runState: v?.runState ?? "idle", answer: v?.answer } } as FlowNode;
    });
    const viewEdges = edges.map((e) => {
      const onPath = pathEdges.has(e.id);
      const branch = e.data?.branch ?? "next";
      const base = { ...e, ...edgeStyle(branch, e.id === activeEdge || (onPath && run?.status === "running")) };
      if (run && !onPath) return { ...base, style: { ...base.style, opacity: 0.25 } };
      if (onPath) return { ...base, style: { ...base.style, strokeWidth: 3.5, opacity: 1 } };
      return base;
    });
    return { viewNodes, viewEdges };
  }, [nodes, edges, run]);

  return (
    <div className="flex h-dvh flex-col">
      <header className="flex flex-wrap items-center gap-2 border-b bg-background px-4 py-2">
        <h1 className="mr-3 text-base font-semibold">AI Decision Flow</h1>
        <Button size="sm" variant="outline" onClick={() => addNode("decision")}><CircleHelp /> Decision</Button>
        <Button size="sm" variant="outline" onClick={() => addNode("end")}><Flag /> Outcome</Button>
        <span className="mx-1 h-5 w-px bg-border" />
        <Button size="sm" variant="outline" onClick={saveAs}><Save /> Save</Button>
        <label className="flex items-center gap-1.5 text-sm">
          <FolderOpen className="size-4 text-muted-foreground" />
          <select
            aria-label="Load a saved workflow"
            className="h-7 rounded-md border bg-background px-2 text-sm"
            value=""
            onChange={(e) => {
              const g = saved[e.target.value];
              if (g) {
                loadGraph(g);
                flash(`Loaded "${e.target.value}"`);
              }
            }}
          >
            <option value="">Load…</option>
            {Object.keys(saved).map((name) => <option key={name} value={name}>{name}</option>)}
          </select>
        </label>
        <Button size="sm" variant="ghost" onClick={exportJson}><Download /> Export JSON</Button>
        <Button size="sm" variant="ghost" onClick={() => fileRef.current?.click()}><Upload /> Import JSON</Button>
        <input ref={fileRef} type="file" accept="application/json,.json" className="hidden"
          onChange={(e) => { importJson(e.target.files?.[0]); e.target.value = ""; }} />
        <Button size="sm" variant="ghost" onClick={() => loadGraph(EXAMPLE_GRAPH)}><RotateCcw /> Example</Button>
        {notice && <span className="ml-auto rounded-md bg-slate-900 px-2 py-1 text-xs text-white">{notice}</span>}
      </header>
      <div className="flex min-h-0 flex-1">
        <div className="min-w-0 flex-1">
          <ReactFlow
            nodes={viewNodes}
            edges={viewEdges}
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            deleteKeyCode={["Backspace", "Delete"]}
            fitView
            fitViewOptions={{ padding: 0.12 }}
          >
            <Background gap={20} />
            <Controls />
            <MiniMap pannable zoomable />
          </ReactFlow>
        </div>
        <RunPanel
          input={input}
          onInput={setInput}
          onRun={() => start(input)}
          busy={busy}
          run={run}
          problems={problems}
          history={history}
          onPickHistory={pickHistory}
          onRerun={(text) => { setInput(text); start(text); }}
        />
      </div>
    </div>
  );
}

export function FlowEditor() {
  return (
    <ReactFlowProvider>
      <Editor />
    </ReactFlowProvider>
  );
}
