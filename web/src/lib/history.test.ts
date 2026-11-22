import { describe, expect, it } from "vitest";
import type { TurnOut } from "@/api/types";
import { turnsToMessages } from "./history";

const turn = (over: Partial<TurnOut>): TurnOut => ({
  id: "t1", conversation_id: "c1", question: "Hỏi?", status: "answered", answer: "Câu một [S1]. Câu hai [S1].",
  missing: null, citations: [], warnings: [], scope: [], latency_ms: 1000, created_at: "2026-11-20T00:00:00Z", ...over,
});

describe("turnsToMessages", () => {
  it("pairs each question with its answer", () => {
    const messages = turnsToMessages([turn({}), turn({ id: "t2" })]);
    expect(messages.map((m) => m.role)).toEqual(["user", "assistant", "user", "assistant"]);
  });

  it("restores flagged sentences as unsupported", () => {
    const [, answer] = turnsToMessages([turn({ warnings: [{ sentence_index: 1, reason: "thiếu nguồn" }] })]);
    const verification = answer.parts.find((p) => p.type === "data-verification");
    expect(verification?.type === "data-verification" && verification.data.sentences).toEqual([
      { index: 0, supported: true, reason: "" },
      { index: 1, supported: false, reason: "thiếu nguồn" },
    ]);
  });

  it("does not claim a check the Validator never made", () => {
    const cite = { label: "S1", chunk_id: "c", document_id: "d", document_title: "hd.pdf", version_id: "v", section: "Điều 5", page: 1 };
    const [, unchecked] = turnsToMessages([turn({ citations: [{ ...cite, verdict: "unchecked" }] })]);
    const [, checked] = turnsToMessages([turn({ citations: [{ ...cite, verdict: "supported" }] })]);
    expect(unchecked.parts.some((p) => p.type === "data-verification")).toBe(false);
    expect(checked.parts.some((p) => p.type === "data-verification")).toBe(true);
  });

  it("marks a failed turn without inventing an answer", () => {
    const [, answer] = turnsToMessages([turn({ status: "failed", answer: null })]);
    expect(answer.parts).toEqual([{ type: "data-turn", data: expect.objectContaining({ status: "failed" }) }]);
  });
});
