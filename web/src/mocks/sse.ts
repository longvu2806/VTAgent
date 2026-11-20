// Turns a scripted stream into the bytes of an AI SDK UI Message Stream (SSE).
import type { Step } from "./scenarios";

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export function sseStream(steps: Step[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let cancelled = false;
  return new ReadableStream({
    async start(controller) {
      for (const { chunk, delay } of steps) {
        if (delay) await sleep(delay);
        if (cancelled) return;
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(chunk)}\n\n`));
      }
      controller.enqueue(encoder.encode("data: [DONE]\n\n"));
      controller.close();
    },
    cancel() {
      cancelled = true; // the user pressed stop
    },
  });
}

export const SSE_HEADERS = {
  "content-type": "text/event-stream",
  "cache-control": "no-cache",
  "x-vercel-ai-ui-message-stream": "v1",
};
