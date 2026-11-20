// Scripted answers for the browser mock. A plan describes one answer; script() turns it
// into the UI Message Stream steps (each with the delay before it) and the turn record the
// API would store, so the same plan drives the live stream, the history and the exports.
import type { StageData, VTChunk } from "@/api/stream";
import type { CitationOut, TurnOut } from "@/api/types";
import { splitSentences } from "@/lib/answer";
import { cite } from "./fixtures";

export interface Step {
  chunk: VTChunk;
  delay: number;
}

const NOT_FOUND = "Không tìm thấy thông tin này trong tài liệu đã nạp.";

interface ToolRun {
  name: string;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
}

interface Plan {
  retrieveDetail: string;
  analyst?: ToolRun[];
  drafts: string[]; // one per round; a second round means the first failed verification
  retryDetail?: string;
  answer: string; // the verified answer
  citations: CitationOut[];
  unsupported?: { index: number; reason: string }[];
  status: "answered" | "partial" | "not_found";
  missing?: string;
  error?: string; // the stream breaks after the first draft
}

const TOKEN_MS = 28;
const stage = (data: StageData, delay = 500): Step => ({ chunk: { type: "data-stage", id: "stage", data }, delay });

function stream(kind: "reasoning" | "text", id: string, text: string, tokenMs = TOKEN_MS): Step[] {
  const words = text.match(/\S+\s*/g) ?? [];
  return [
    { chunk: { type: `${kind}-start`, id }, delay: 0 },
    ...words.map((delta) => ({ chunk: { type: `${kind}-delta`, id, delta } as VTChunk, delay: tokenMs })),
    { chunk: { type: `${kind}-end`, id }, delay: 0 },
  ];
}

const PENALTY =
  "Bên B chịu phạt **0,05% giá trị phần hàng giao chậm cho mỗi ngày chậm** [S1]. " +
  "Tổng mức phạt không vượt quá 8% giá trị phần nghĩa vụ bị vi phạm [S1]. " +
  "Mức trần này trùng với giới hạn của Luật Thương mại [S2].";
const WARRANTY =
  "Thiết bị được bảo hành **24 tháng kể từ ngày hai bên ký biên bản nghiệm thu** [S1]. " +
  "Trong thời hạn đó, Bên B phải sửa chữa hoặc thay thế thiết bị lỗi trong vòng 07 ngày làm việc kể từ khi nhận thông báo [S2].";

const PLANS: { match: RegExp; plan: () => Plan }[] = [
  {
    match: /lỗi|thử lỗi/i,
    plan: () => ({
      retrieveDetail: "4 tài liệu", drafts: ["Theo hợp đồng, Bên B"], answer: "", citations: [], status: "answered",
      error: "Mô hình không phản hồi trong 300 giây. Câu trả lời chưa hoàn tất.",
    }),
  },
  {
    match: /tính|bao nhiêu tiền|chậm \d+ ngày/i,
    plan: () => ({
      retrieveDetail: "Hợp đồng 12/2026/HĐMB",
      analyst: [{
        name: "calculate",
        input: {
          expression: "gia_tri * ty_le_ngay * so_ngay",
          operands: {
            gia_tri: { value: "2500000000", sid: "S1" },
            ty_le_ngay: { value: "0.0005", sid: "S2" },
            so_ngay: { value: "15", sid: "user" },
          },
        },
        output: { value: "18750000" },
      }],
      drafts: [
        "Tiền phạt khi giao chậm 15 ngày là **18.750.000 đồng**, tính bằng giá trị hợp đồng 2.500.000.000 đồng [S1] nhân mức phạt 0,05% mỗi ngày [S2] nhân 15 ngày. " +
          "Số tiền này thấp hơn trần 8% giá trị nghĩa vụ bị vi phạm [S2].",
      ],
      answer:
        "Tiền phạt khi giao chậm 15 ngày là **18.750.000 đồng**, tính bằng giá trị hợp đồng 2.500.000.000 đồng [S1] nhân mức phạt 0,05% mỗi ngày [S2] nhân 15 ngày. " +
        "Số tiền này thấp hơn trần 8% giá trị nghĩa vụ bị vi phạm [S2].",
      citations: [cite("S1", "c-hd-3-1"), cite("S2", "c-hd-8-2")],
      status: "answered",
    }),
  },
  {
    match: /bảo hành|vòng 2/i,
    plan: () => ({
      retrieveDetail: "4 tài liệu",
      drafts: ["Thiết bị được bảo hành 12 tháng kể từ ngày giao hàng [S1]. Bên B sửa chữa thiết bị lỗi trong 07 ngày [S2].", WARRANTY],
      retryDetail: "1 câu sai thời hạn",
      answer: WARRANTY,
      citations: [cite("S1", "c-hd-9-1"), cite("S2", "c-hd-9-2")],
      status: "answered",
    }),
  },
  {
    match: /nghỉ phép/i,
    plan: () => ({
      retrieveDetail: "Quy chế nghỉ phép năm 2026",
      drafts: ["Người lao động làm việc đủ 12 tháng được nghỉ phép năm **12 ngày làm việc**, hưởng nguyên lương [S1]."],
      answer: "Người lao động làm việc đủ 12 tháng được nghỉ phép năm **12 ngày làm việc**, hưởng nguyên lương [S1].",
      citations: [cite("S1", "c-qc-3-1")],
      status: "partial",
      missing: "Quy chế không nói số ngày nghỉ phép được cộng thêm theo thâm niên.",
    }),
  },
  {
    match: /doanh thu|lợi nhuận/i,
    plan: () => {
      const text =
        "Doanh thu thuần quý III/2026 đạt **48,6 tỷ đồng**, tăng 12% so với cùng kỳ năm trước [S1]. " +
        "Lợi nhuận sau thuế tăng 20% nhờ giảm chi phí bảo trì [S1].";
      return {
        retrieveDetail: "Báo cáo quý III/2026",
        drafts: [text, text],
        retryDetail: "1 câu thiếu căn cứ",
        answer: text,
        citations: [cite("S1", "c-bc-2-1")],
        unsupported: [{ index: 1, reason: "Đoạn được trích không nói gì về lợi nhuận sau thuế." }],
        status: "answered",
      };
    },
  },
  {
    match: /lương|thưởng|bảo hiểm/i,
    plan: () => ({ retrieveDetail: "4 tài liệu", drafts: [], answer: NOT_FOUND, citations: [], status: "not_found" }),
  },
  {
    match: /.*/,
    plan: () => ({
      retrieveDetail: "4 tài liệu", drafts: [PENALTY], answer: PENALTY,
      citations: [cite("S1", "c-hd-8-2"), cite("S2", "c-ltm-301")], status: "answered",
    }),
  },
];

export function script(question: string, ids: { turnId: string; conversationId: string; scope: string[] }) {
  const plan = PLANS.find((p) => p.match.test(question))!.plan();
  const analyst = plan.analyst !== undefined;
  const steps: Step[] = [
    { chunk: { type: "start", messageId: ids.turnId }, delay: 0 },
    stage({ node: "route", round: 1 }, 250),
  ];
  if (analyst) steps.push(stage({ node: "plan", round: 1 }, 600));
  steps.push(stage({ node: "retrieve", round: 1, detail: plan.retrieveDetail }, 500));
  plan.analyst?.forEach((tool, i) => {
    const toolCallId = `${ids.turnId}-tool-${i}`;
    steps.push(
      stage({ node: "tools", round: 1 }, 700),
      { chunk: { type: "tool-input-available", toolCallId, toolName: tool.name, input: tool.input, dynamic: true }, delay: 0 },
      { chunk: { type: "tool-output-available", toolCallId, output: tool.output, dynamic: true }, delay: 500 },
    );
  });

  plan.drafts.forEach((draft, i) => {
    const round = i + 1;
    if (round > 1) {
      steps.push(stage({ node: "retry", round, detail: plan.retryDetail }, 900), { chunk: { type: "reset-step" }, delay: 0 });
    }
    steps.push(
      stage({ node: analyst ? "interpret" : "answer", round }, 700),
      { chunk: { type: "start-step" }, delay: 0 },
      ...stream("reasoning", `draft-${round}`, plan.error ? `${draft} ` : draft),
      { chunk: { type: "finish-step" }, delay: 0 },
    );
    if (!plan.error) steps.push(stage({ node: "verify", round }, 300));
  });

  const turn: TurnOut = {
    id: ids.turnId, conversation_id: ids.conversationId, question, status: plan.status, answer: plan.answer,
    missing: plan.missing ?? null, citations: plan.citations,
    warnings: (plan.unsupported ?? []).map((u) => ({ sentence_index: u.index, reason: u.reason })),
    scope: ids.scope, latency_ms: null, created_at: new Date().toISOString(),
  };

  if (plan.error) {
    steps.push({ chunk: { type: "error", errorText: plan.error }, delay: 1500 });
    return { steps, turn: { ...turn, status: "failed" as const, answer: null } };
  }

  const unsupported = new Map((plan.unsupported ?? []).map((u) => [u.index, u.reason]));
  const sentences = plan.status === "not_found" ? [] : splitSentences(plan.answer);
  steps.push(
    {
      chunk: {
        type: "data-verification", id: "verification",
        data: { sentences: sentences.map((_, index) => ({ index, supported: !unsupported.has(index), reason: unsupported.get(index) ?? "" })) },
      },
      delay: plan.status === "not_found" ? 300 : 1000,
    },
    stage({ node: "finalize", round: Math.max(plan.drafts.length, 1) }, 0),
    ...stream("text", "answer", plan.answer, 0),
    { chunk: { type: "data-citations", id: "citations", data: plan.citations }, delay: 0 },
  );
  const latency = steps.reduce((t, s) => t + s.delay, 0);
  turn.latency_ms = latency;
  steps.push(
    { chunk: { type: "data-turn", id: "turn", data: { id: ids.turnId, status: plan.status, missing: turn.missing, latency_ms: latency } }, delay: 0 },
    { chunk: { type: "finish" }, delay: 0 },
  );
  return { steps, turn };
}

/** Questions that trigger each scripted answer; shown on the start page in mock mode. */
export const SAMPLE_QUESTIONS = [
  "Bên B bị phạt thế nào khi giao hàng chậm?",
  "Thời hạn bảo hành thiết bị là bao lâu?",
  "Giao chậm 15 ngày thì bị phạt bao nhiêu tiền?",
  "Người lao động được nghỉ phép năm bao nhiêu ngày?",
  "Doanh thu và lợi nhuận quý III thế nào?",
  "Thưởng Tết năm nay là bao nhiêu?",
  "Thử lỗi khi mô hình không phản hồi",
];
