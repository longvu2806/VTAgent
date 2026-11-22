// Rebuild chat messages from stored turns, so a reopened conversation shows its answers
// with the same chips and warnings as when they streamed.
import type { VTMessage } from "@/api/stream";
import type { TurnOut } from "@/api/types";
import { splitSentences } from "./answer";

export function turnsToMessages(turns: TurnOut[]): VTMessage[] {
  return turns.flatMap((t): VTMessage[] => {
    const question: VTMessage = { id: `q-${t.id}`, role: "user", parts: [{ type: "text", text: t.question }] };
    const status = { type: "data-turn", data: { id: t.id, status: t.status, missing: t.missing, latency_ms: t.latency_ms } } as const;
    if (t.answer === null) return [question, { id: t.id, role: "assistant", parts: [status] }]; // a failed turn
    const flagged = new Map(t.warnings.map((w) => [w.sentence_index, w.reason]));
    const sentences = t.status === "not_found" ? [] : splitSentences(t.answer);
    // An answer the Validator never saw has only unchecked citations and no warnings.
    const verified = t.warnings.length > 0 || t.citations.some((c) => c.verdict !== "unchecked");
    const answer: VTMessage = {
      id: t.id,
      role: "assistant",
      parts: [
        ...(verified
          ? [
              {
                type: "data-verification" as const,
                data: {
                  sentences: sentences.map((_, index) => ({
                    index,
                    supported: !flagged.has(index),
                    reason: flagged.get(index) ?? "",
                  })),
                },
              },
            ]
          : []),
        { type: "text", text: t.answer, state: "done" },
        { type: "data-citations", data: t.citations },
        status,
      ],
    };
    return [question, answer];
  });
}
