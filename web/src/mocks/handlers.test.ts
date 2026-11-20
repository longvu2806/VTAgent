// The browser mock is the API contract the UI is built against, so its handlers are
// checked through HTTP like the real API will be.
import { setupServer } from "msw/node";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import type { ConversationDetail, ReviewRunOut, RuleOut } from "@/api/types";
import { handlers } from "./handlers";

// MSW refuses to declare SSE handlers without EventSource; the job stream is not called here.
vi.hoisted(() => {
  globalThis.EventSource ??= class {} as unknown as typeof EventSource;
});

const server = setupServer(...handlers);
beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterAll(() => server.close());

const call = (path: string, init?: RequestInit) =>
  fetch(`${location.origin}/api/v1${path}`, { ...init, headers: { "content-type": "application/json" } });
const json = async <T>(path: string, init?: RequestInit) => (await call(path, init)).json() as Promise<T>;

describe("mock API", () => {
  it("streams answers as an AI SDK UI message stream", async () => {
    const res = await call("/conversations/c-1/turns", {
      method: "POST",
      body: JSON.stringify({ question: "Bên B bị phạt thế nào?", document_ids: [] }),
    });
    expect(res.headers.get("x-vercel-ai-ui-message-stream")).toBe("v1");
    const reader = res.body!.getReader();
    const first = new TextDecoder().decode((await reader.read()).value);
    await reader.cancel();
    expect(first).toMatch(/^data: \{"type":"start"/);
  });

  it("deletes the answers citing a deleted document (BR10)", async () => {
    expect((await json<ConversationDetail>("/conversations/c-3")).turns).toHaveLength(1);
    expect((await call("/documents/doc-qc", { method: "DELETE" })).status).toBe(204);
    expect((await json<ConversationDetail>("/conversations/c-3")).turns).toHaveLength(0);
    const gone = await call("/documents/doc-qc");
    expect(gone.status).toBe(404);
    expect(gone.headers.get("content-type")).toBe("application/problem+json");
  });

  it("switches a rule off instead of deleting it (BR18)", async () => {
    const rule = await json<RuleOut>("/rules/contract.penalty_cap", {
      method: "PATCH",
      body: JSON.stringify({ enabled: false }),
    });
    expect(rule.enabled).toBe(false);
    expect((await json<RuleOut[]>("/rules")).find((r) => r.id === rule.id)?.enabled).toBe(false);
  });

  it("runs a review, then reports findings with the passages behind them", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout"] });
    const started = await json<ReviewRunOut>("/documents/doc-hd/reviews", { method: "POST" });
    expect(started.status).toBe("running");
    vi.runAllTimers();
    vi.useRealTimers();
    const done = await json<ReviewRunOut>(`/reviews/${started.id}`);
    expect(done.status).toBe("done");
    // The penalty-cap rule was switched off above, so only the payment term is measured.
    expect(done.findings.find((f) => f.rule_id === "contract.payment_term")?.passages).toEqual(["c-hd-7-1"]);
    expect(done.findings.some((f) => f.rule_id === "contract.penalty_cap")).toBe(false);
  });
});
