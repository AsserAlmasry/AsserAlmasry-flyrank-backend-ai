import { inngest } from "./client";

export const ping = inngest.createFunction(
  { id: "ping", triggers: [{ event: "test/ping" }] },
  async ({ step }) => {
    await step.sleep("wait-a-moment", "1s");
    return { pong: true };
  },
);

export const functions = [ping];
