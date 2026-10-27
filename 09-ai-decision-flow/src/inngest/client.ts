import { Inngest } from "inngest";

// isDev: talk to the local Inngest Dev Server (no account, no signing key) unless we're in production.
export const inngest = new Inngest({
  id: "ai-decision-flow",
  isDev: process.env.NODE_ENV !== "production" || process.env.INNGEST_DEV === "1",
});
