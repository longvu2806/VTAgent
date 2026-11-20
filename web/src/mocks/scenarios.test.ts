import { readUIMessageStream } from "ai";
import { describe, expect, it } from "vitest";
import type { VTChunk, VTMessage } from "@/api/stream";
import { SAMPLE_QUESTIONS, script } from "./scenarios";

async function run(question: string) {
  const { steps, turn } = script(question, { turnId: "t1", conversationId: "c1", scope: [] });
  const stream = new ReadableStream<VTChunk>({
    start(controller) {
      steps.forEach((s) => controller.enqueue(s.chunk));
      controller.close();
    },
  });
  let message: VTMessage | undefined;
  const errors: unknown[] = [];
  for await (const m of readUIMessageStream<VTMessage>({ stream, onError: (e) => errors.push(e) })) message = m;
  const parts = message?.parts ?? [];
  const text = parts.flatMap((p) => (p.type === "text" ? [p.text] : [])).join("");
  return { parts, text, turn, errors };
}

describe("mock answer scripts", () => {
  it.each(SAMPLE_QUESTIONS.filter((q) => !/lỗi/.test(q)))("cites only known sources: %s", async (question) => {
    const { text, turn } = await run(question);
    expect(text).toBe(turn.answer);
    const labels = new Set([...text.matchAll(/S\d+/g)].map((m) => m[0]));
    expect([...labels].sort()).toEqual(turn.citations.map((c) => c.label).sort());
  });

  it("drops the round-1 draft on reset-step", async () => {
    const { parts } = await run("Thời hạn bảo hành thiết bị là bao lâu?");
    const drafts = parts.filter((p) => p.type === "reasoning");
    expect(drafts).toHaveLength(1);
    expect(drafts[0].type === "reasoning" && drafts[0].text).toContain("24 tháng");
  });

  it("keeps one stage part, updated in place", async () => {
    const { parts } = await run("Bên B bị phạt thế nào khi giao hàng chậm?");
    expect(parts.filter((p) => p.type === "data-stage")).toHaveLength(1);
  });

  it("marks a partial answer with what is missing", async () => {
    const { turn } = await run("Người lao động được nghỉ phép năm bao nhiêu ngày?");
    expect(turn.status).toBe("partial");
    expect(turn.missing).toBeTruthy();
  });

  it("refuses without citations when nothing is found", async () => {
    const { text, turn } = await run("Thưởng Tết năm nay là bao nhiêu?");
    expect(turn.status).toBe("not_found");
    expect(turn.citations).toEqual([]);
    expect(text).toMatch(/^Không tìm thấy/);
  });

  it("streams the analyst's calculation as a tool part", async () => {
    const { parts } = await run("Giao chậm 15 ngày thì bị phạt bao nhiêu tiền?");
    const tool = parts.find((p) => p.type === "dynamic-tool");
    expect(tool?.type === "dynamic-tool" && tool.state).toBe("output-available");
  });

  it("ends with an error and no answer when the model fails", async () => {
    const { text, turn, errors } = await run("Thử lỗi khi mô hình không phản hồi");
    expect(text).toBe("");
    expect(turn.status).toBe("failed");
    expect(errors).toHaveLength(1);
  });
});
