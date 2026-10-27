import OpenAI from "openai";

export function llmClient(): OpenAI {
  return new OpenAI({
    baseURL: process.env.LLM_BASE_URL,
    apiKey: process.env.LLM_API_KEY,
    timeout: 30_000, // the SDK default is 10 minutes: far too long for one workflow step
    maxRetries: 0, // retries are Inngest's job (per step), so we don't stack two retry layers
  });
}
