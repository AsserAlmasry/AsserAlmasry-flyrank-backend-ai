"use client";

import dynamic from "next/dynamic";

// The editor reads localStorage and measures the canvas, so it only makes sense in the browser.
export const FlowClient = dynamic(() => import("@/components/flow/flow-editor").then((m) => m.FlowEditor), {
  ssr: false,
  loading: () => <div className="grid h-dvh place-items-center text-sm text-muted-foreground">Loading editor…</div>,
});
