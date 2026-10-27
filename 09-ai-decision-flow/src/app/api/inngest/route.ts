import { serve } from "inngest/next";
import { inngest } from "@/inngest/client";
import { functions } from "@/inngest/functions";

// The Dev Server discovers and calls our functions through this endpoint.
export const { GET, POST, PUT } = serve({ client: inngest, functions });
