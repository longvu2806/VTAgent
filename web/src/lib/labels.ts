// Vietnamese wording for values that come from the API.
import type { StageData } from "@/api/stream";
import type { Genre, OutlineNode, RelationType, RuleCondition, Severity, ValidityStatus } from "@/api/types";

export const GENRE: Record<Genre, string> = {
  law: "Văn bản pháp luật",
  contract: "Hợp đồng",
  policy: "Quy chế, quy trình",
  report: "Báo cáo",
  technical: "Tài liệu kỹ thuật",
  unknown: "Chưa xác định thể loại",
};

export const VALIDITY: Record<ValidityStatus, string> = {
  in_force: "Còn hiệu lực",
  partly_expired: "Hết hiệu lực một phần",
  expired: "Hết hiệu lực",
  unknown: "Chưa rõ hiệu lực",
};

export const RELATION: Record<RelationType, string> = {
  amends: "Sửa đổi",
  supplements: "Bổ sung",
  replaces: "Thay thế",
  repeals: "Bãi bỏ",
  guides: "Hướng dẫn",
};

export const SEVERITY: Record<Severity, string> = { high: "Nghiêm trọng", medium: "Cần lưu ý", low: "Thấp" };

export const CONDITION: Record<RuleCondition["type"], string> = {
  missing_clause: "Thiếu điều khoản",
  required_metadata: "Thiếu thông tin bắt buộc",
  max_percent: "Tỷ lệ vượt mức",
  max_amount: "Số tiền vượt mức",
  max_days: "Số ngày vượt mức",
  sum_mismatch: "Tổng trong bảng không khớp",
};

const quoted = (s: string) => `“${s}”`;

export function conditionText(c: RuleCondition): string {
  switch (c.type) {
    case "missing_clause": return `Không có điều khoản nào chứa ${c.patterns.map(quoted).join(", ")}`;
    case "required_metadata": return `Thiếu trường ${c.field}`;
    case "max_percent": return `Tỷ lệ gần ${quoted(c.near)} vượt ${c.max}%`;
    case "max_amount": return `Số tiền gần ${quoted(c.near)} vượt ${c.max.toLocaleString("vi-VN")} đồng`;
    case "max_days": return `Số ngày gần ${quoted(c.near)} vượt ${c.max} ngày`;
    case "sum_mismatch": return `Tổng của bảng ${quoted(c.table_pattern)} không khớp các dòng`;
  }
}

const OUTLINE_LEVEL: Record<OutlineNode["level"], string> = {
  document: "", part: "Phần", chapter: "Chương", section: "Mục", article: "Điều",
  clause: "Khoản", point: "Điểm", appendix: "Phụ lục", heading: "",
};

/** "Điều 8. Phạt vi phạm", "Khoản 2", "II. Kết quả kinh doanh". */
export function outlineLabel(n: OutlineNode): string {
  const prefix = OUTLINE_LEVEL[n.level];
  const number = n.number ? [prefix, n.number].filter(Boolean).join(" ") : prefix;
  return [number, n.title].filter(Boolean).join(". ");
}

export const outlineUnit = (level: OutlineNode["level"]) => OUTLINE_LEVEL[level].toLowerCase();

export const formatDate = (iso: string) => new Intl.DateTimeFormat("vi-VN", { dateStyle: "medium" }).format(new Date(iso));
export const formatTime = (iso: string) =>
  new Intl.DateTimeFormat("vi-VN", { dateStyle: "short", timeStyle: "short" }).format(new Date(iso));

export function stageText({ node, round, detail }: StageData): string {
  switch (node) {
    case "route": return "Đang hiểu câu hỏi";
    case "retrieve": return detail ? `Đang tìm trong ${detail}` : "Đang tìm bằng chứng";
    case "answer": return round > 1 ? "Đang soạn lại" : "Đang soạn câu trả lời";
    case "plan": return "Đang lập kế hoạch phân tích";
    case "tools": return "Đang tính toán và đối chiếu";
    case "interpret": return "Đang diễn giải kết quả";
    case "verify": return "Đang đối chiếu từng câu với nguồn";
    case "retry": return `Đang soạn lại để bổ sung căn cứ${detail ? ` (${detail})` : ""}`;
    case "finalize": return "Đang hoàn tất";
  }
}
