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
import { CircleHelp, Flag, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { nodeTypes } from "@/components/flow/nodes";
import { edgeStyle, EXAMPLE_GRAPH, fromGraph, toGraph, type Branch, type FlowEdge, type FlowNode } from "@/lib/flow";

const AUTOSAVE_KEY = "ai-decision-flow:current";

function loadInitial() {
  try {
    const saved = localStorage.getItem(AUTOSAVE_KEY);
    if (saved) return fromGraph(JSON.parse(saved));
  } catch {
    /* private mode or bad JSON: fall back to the example */
  }
  return fromGraph(EXAMPLE_GRAPH);
}

function Editor() {
  const [nodes, setNodes, onNodesChange] = useNodesState<FlowNode>(fromGraph(EXAMPLE_GRAPH).nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState<FlowEdge>(fromGraph(EXAMPLE_GRAPH).edges);
  const [loaded, setLoaded] = useState(false);

  // Load the autosaved graph once on the client (localStorage doesn't exist during server rendering).
  useEffect(() => {
    const initial = loadInitial();
    setNodes(initial.nodes);
    setEdges(initial.edges);
    setLoaded(true);
  }, [setNodes, setEdges]);

  // Store graph state locally on every change.
  useEffect(() => {
    if (!loaded) return;
    try {
      localStorage.setItem(AUTOSAVE_KEY, JSON.stringify(toGraph(nodes, edges)));
    } catch {
      /* storage full or blocked: editing still works, it just won't persist */
    }
  }, [nodes, edges, loaded]);

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
    const y = 80 + (nodes.length % 6) * 70;
    const node =
      type === "decision"
        ? { id, type, position: { x: 420, y }, data: { label: "New question", prompt: "" } }
        : { id, type, position: { x: 820, y }, data: { label: "New outcome" } };
    setNodes((ns) => [...ns, node as FlowNode]);
  };

  const reset = () => {
    const g = fromGraph(EXAMPLE_GRAPH);
    setNodes(g.nodes);
    setEdges(g.edges);
  };

  return (
    <div className="flex h-dvh flex-col">
      <header className="flex flex-wrap items-center gap-2 border-b bg-background px-4 py-2">
        <h1 className="mr-4 text-base font-semibold">AI Decision Flow</h1>
        <Button size="sm" variant="outline" onClick={() => addNode("decision")}>
          <CircleHelp /> Decision
        </Button>
        <Button size="sm" variant="outline" onClick={() => addNode("end")}>
          <Flag /> Outcome
        </Button>
        <Button size="sm" variant="ghost" onClick={reset}>
          <RotateCcw /> Example
        </Button>
      </header>
      <div className="flex-1">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          deleteKeyCode={["Backspace", "Delete"]}
          fitView
          fitViewOptions={{ padding: 0.15 }}
        >
          <Background gap={20} />
          <Controls />
          <MiniMap pannable zoomable />
        </ReactFlow>
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
