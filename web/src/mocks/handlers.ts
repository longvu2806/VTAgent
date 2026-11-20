// The browser mock of the VTAgent API (SDD §9.2), backed by in-memory fixtures.
import { http, HttpResponse, sse } from "msw";
import type { ConversationDetail, ConversationOut, RuleIn, RuleOut, TurnOut } from "@/api/types";
import { conversations, documents, outlines, passages, reviews, rules, turns } from "./fixtures";
import { reviewExport, turnExport } from "./exports";
import { createJob, jobEvents } from "./ingest";
import { startReview } from "./review";
import { script } from "./scenarios";
import { SSE_HEADERS, sseStream } from "./sse";

const API = "/api/v1";

const problem = (status: number, code: string, detail: string) =>
  HttpResponse.json({ type: "about:blank", title: code, status, detail, code }, {
    status, headers: { "content-type": "application/problem+json" },
  });
const notFound = (what: string) => problem(404, "not_found", `Không có ${what}.`);

const download = (body: string, format: string, name: string) =>
  new HttpResponse(body, {
    headers: {
      "content-type": format === "json" ? "application/json" : "text/markdown; charset=utf-8",
      "content-disposition": `attachment; filename="${name}.${format}"`,
    },
  });

const allTurns = () => Object.values(turns).flat();

// History of the sample conversations, built from the same scripts as live answers.
const SEED: Record<string, string> = {
  "c-1": "Bên B bị phạt thế nào khi giao hàng chậm?",
  "c-2": "Thời hạn bảo hành thiết bị là bao lâu?",
  "c-3": "Người lao động được nghỉ phép năm bao nhiêu ngày?",
};
for (const [conversationId, question] of Object.entries(SEED)) {
  const created = conversations.find((c) => c.id === conversationId)!.updated_at;
  const { turn } = script(question, { turnId: `t-${conversationId}`, conversationId, scope: [] });
  turns[conversationId] = [{ ...turn, created_at: created }];
}

export const handlers = [
  // Documents
  http.get(`${API}/documents`, () => HttpResponse.json({ items: documents, next_cursor: null })),

  http.post(`${API}/documents`, async ({ request }) => {
    const files = (await request.formData()).getAll("files").filter((f): f is File => f instanceof File);
    return HttpResponse.json({ jobs: files.map((f) => createJob(f)) }, { status: 202 });
  }),

  http.get(`${API}/documents/:id`, ({ params }) => {
    const document = documents.find((d) => d.id === params.id);
    return document ? HttpResponse.json(document) : notFound("tài liệu này");
  }),

  http.delete(`${API}/documents/:id`, ({ params }) => {
    const at = documents.findIndex((d) => d.id === params.id);
    if (at < 0) return notFound("tài liệu này");
    documents.splice(at, 1);
    delete reviews[params.id as string];
    // BR10: answers that cite the deleted document go with it.
    for (const id of Object.keys(turns)) {
      turns[id] = turns[id].filter((t) => !t.citations.some((c) => c.document_id === params.id));
    }
    return new HttpResponse(null, { status: 204 });
  }),

  http.get(`${API}/documents/:id/outline`, ({ params }) => {
    const outline = outlines[params.id as string];
    return outline ? HttpResponse.json(outline) : notFound("cây cấu trúc");
  }),

  http.get(`${API}/documents/:id/file`, async ({ params }) => {
    if (params.id !== "doc-hd") return notFound("tệp gốc trong dữ liệu mẫu");
    const pdf = await fetch("/mock/hop-dong-mau.pdf").then((r) => r.arrayBuffer());
    return new HttpResponse(pdf, { headers: { "content-type": "application/pdf" } });
  }),

  http.post(`${API}/documents/:id/versions`, async ({ params, request }) => {
    if (!documents.some((d) => d.id === params.id)) return notFound("tài liệu này");
    const file = (await request.formData()).get("file");
    if (!(file instanceof File)) return problem(400, "invalid_request", "Thiếu tệp.");
    return HttpResponse.json(createJob(file, params.id as string), { status: 202 });
  }),

  // MSW opens the stream only after the resolver returns, so events are scheduled, not awaited.
  sse<{ stage: string; done: string; failed: string }>(`${API}/jobs/:id/events`, ({ params, client }) => {
    let at = 0;
    for (const { event, delay } of jobEvents(params.id as string)) {
      at += delay;
      setTimeout(() => client.send({ event: event.event, data: JSON.stringify(event.data) }), at);
    }
    setTimeout(() => client.close(), at + 50);
  }),

  // Reviews
  http.post(`${API}/documents/:id/reviews`, ({ params }) =>
    documents.some((d) => d.id === params.id)
      ? HttpResponse.json(startReview(params.id as string), { status: 202 })
      : notFound("tài liệu này")),

  http.get(`${API}/documents/:id/reviews/latest`, ({ params }) => {
    const run = reviews[params.id as string];
    return run ? HttpResponse.json(run) : notFound("lần rà soát nào");
  }),

  http.get(`${API}/reviews/:id`, ({ params }) => {
    const run = Object.values(reviews).find((r) => r.id === params.id);
    return run ? HttpResponse.json(run) : notFound("lần rà soát này");
  }),

  http.get(`${API}/reviews/:id/export`, ({ params, request }) => {
    const run = Object.values(reviews).find((r) => r.id === params.id);
    const document = documents.find((d) => d.id === run?.document_id);
    if (!run || !document) return notFound("lần rà soát này");
    const format = new URL(request.url).searchParams.get("format") === "json" ? "json" : "md";
    return download(reviewExport(run, document, format), format, `ra-soat-${document.id}`);
  }),

  // Rules: no DELETE, a rule can only be disabled (BR18)
  http.get(`${API}/rules`, ({ request }) => {
    const genre = new URL(request.url).searchParams.get("genre");
    return HttpResponse.json(genre ? rules.filter((r) => r.genre === genre) : rules);
  }),

  http.post(`${API}/rules`, async ({ request }) => {
    const rule: RuleOut = { ...((await request.json()) as RuleIn), id: crypto.randomUUID(), updated_at: new Date().toISOString() };
    rules.push(rule);
    return HttpResponse.json(rule, { status: 201 });
  }),

  http.patch(`${API}/rules/:id`, async ({ params, request }) => {
    const rule = rules.find((r) => r.id === params.id);
    if (!rule) return notFound("quy tắc này");
    Object.assign(rule, (await request.json()) as Partial<RuleIn>, { updated_at: new Date().toISOString() });
    return HttpResponse.json(rule);
  }),

  // Conversations
  http.get(`${API}/conversations`, () => {
    const sorted = [...conversations].sort((a, b) => b.updated_at.localeCompare(a.updated_at));
    return HttpResponse.json({ items: sorted, next_cursor: null });
  }),

  http.post(`${API}/conversations`, async ({ request }) => {
    const { title = null } = (await request.json()) as { title?: string | null };
    const now = new Date().toISOString();
    const created: ConversationOut = { id: crypto.randomUUID(), title, pinned: false, created_at: now, updated_at: now };
    conversations.unshift(created);
    turns[created.id] = [];
    return HttpResponse.json(created, { status: 201 });
  }),

  http.get(`${API}/conversations/:id`, ({ params }) => {
    const found = conversations.find((c) => c.id === params.id);
    if (!found) return notFound("hội thoại này");
    const detail: ConversationDetail = { ...found, turns: turns[found.id] ?? [] };
    return HttpResponse.json(detail);
  }),

  http.patch(`${API}/conversations/:id`, async ({ params, request }) => {
    const found = conversations.find((c) => c.id === params.id);
    if (!found) return notFound("hội thoại này");
    Object.assign(found, (await request.json()) as Partial<Pick<ConversationOut, "title" | "pinned">>);
    return HttpResponse.json(found);
  }),

  http.delete(`${API}/conversations/:id`, ({ params }) => {
    const at = conversations.findIndex((c) => c.id === params.id);
    if (at < 0) return notFound("hội thoại này");
    conversations.splice(at, 1);
    delete turns[params.id as string];
    return new HttpResponse(null, { status: 204 });
  }),

  http.post(`${API}/conversations/:conversationId/turns`, async ({ params, request }) => {
    const conversationId = params.conversationId as string;
    const conversation = conversations.find((c) => c.id === conversationId);
    if (!conversation) return notFound("hội thoại này");
    const { question, document_ids } = (await request.json()) as { question: string; document_ids: string[] };
    const { steps, turn } = script(question, { turnId: crypto.randomUUID(), conversationId, scope: document_ids });
    const total = steps.reduce((t, s) => t + s.delay, 0);
    setTimeout(() => {
      (turns[conversationId] ??= []).push(turn as TurnOut);
      conversation.updated_at = new Date().toISOString();
    }, total);
    return new HttpResponse(sseStream(steps), { headers: SSE_HEADERS });
  }),

  http.get(`${API}/turns/:id/export`, ({ params, request }) => {
    const turn = allTurns().find((t) => t.id === params.id);
    if (!turn) return notFound("lượt hỏi đáp này");
    const format = new URL(request.url).searchParams.get("format") === "json" ? "json" : "md";
    return download(turnExport(turn, format), format, `cau-tra-loi-${turn.id.slice(0, 8)}`);
  }),

  http.get(`${API}/passages/:chunkId`, ({ params }) => {
    const passage = passages[params.chunkId as string];
    return passage ? HttpResponse.json(passage) : notFound("đoạn này");
  }),
];
