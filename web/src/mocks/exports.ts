// Export files the API produces for an answer or a review (SDD §10.4).
import type { DocumentOut, ReviewRunOut, TurnOut } from "@/api/types";
import { passages } from "./fixtures";

const DISCLAIMER = "_VTAgent chỉ trả lời từ tài liệu đã nạp và không thay thế tư vấn chuyên môn._";
const SEVERITY = { high: "Cao", medium: "Trung bình", low: "Thấp" } as const;

export function turnExport(turn: TurnOut, format: "md" | "json"): string {
  const sources = turn.citations.map((c) => ({ ...c, passage: passages[c.chunk_id] ?? null }));
  if (format === "json") return JSON.stringify({ ...turn, sources }, null, 2);
  const lines = [`# ${turn.question}`, "", turn.answer ?? "", ""];
  if (turn.missing) lines.push(`**Chưa tìm thấy:** ${turn.missing}`, "");
  if (turn.warnings.length) {
    lines.push("## Câu chưa đủ căn cứ", "", ...turn.warnings.map((w) => `- Câu ${w.sentence_index + 1}: ${w.reason}`), "");
  }
  if (sources.length) {
    lines.push("## Nguồn", "");
    for (const s of sources) {
      lines.push(`- **[${s.label}]** ${s.document_title}, ${s.section}${s.page !== null ? `, trang ${s.page}` : ""}`);
      if (s.passage) lines.push(`  > ${s.passage.text}`);
    }
    lines.push("");
  }
  lines.push(DISCLAIMER);
  return lines.join("\n");
}

export function reviewExport(run: ReviewRunOut, document: DocumentOut, format: "md" | "json"): string {
  if (format === "json") return JSON.stringify({ ...run, document_title: document.title }, null, 2);
  const lines = [`# Kết quả rà soát: ${document.title}`, "", `Thời điểm: ${run.started_at}`, ""];
  if (!run.findings.length) lines.push("Không có phát hiện nào theo các quy tắc đang bật.", "");
  run.findings.forEach((f, i) => {
    lines.push(`## ${i + 1}. ${f.rule_name} (mức ${SEVERITY[f.severity]})`, "", f.description, "");
    if (f.value) lines.push(`Giá trị tìm thấy: ${f.value}`, "");
    lines.push(`Căn cứ: ${f.basis}`, "");
    for (const id of f.passages) {
      const p = passages[id];
      if (p) lines.push(`> ${p.section}${p.page !== null ? `, trang ${p.page}` : ""}: ${p.text}`, "");
    }
  });
  lines.push(DISCLAIMER);
  return lines.join("\n");
}
