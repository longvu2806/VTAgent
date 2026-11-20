// In-memory sample data for the browser mock. All documents are invented for the demo,
// except the short excerpt of Article 301 of the 2005 Commercial Law (public law text).
// The sample contract matches web/public/mock/hop-dong-mau.pdf page by page.
import type {
  CitationOut,
  ConversationOut,
  DocumentDetail,
  OutlineNode,
  PassageOut,
  ReviewRunOut,
  RuleOut,
  TurnOut,
  VersionOut,
} from "@/api/types";

const version = (id: string, seq: number, file: string, pages: number | null, at: string): VersionOut => ({
  id, seq, file_name: file, file_ext: file.slice(file.lastIndexOf(".")), pages, status: "ready", ingested_at: at,
});

export const documents: DocumentDetail[] = [
  {
    id: "doc-hd", title: "Hợp đồng mua bán thiết bị số 12/2026/HĐMB", doc_number: "12/2026/HĐMB",
    genre: "contract", validity_status: "in_force", created_at: "2026-11-02T08:10:00Z",
    current_version: version("v-hd-1", 1, "hop-dong-mua-ban-12-2026.pdf", 6, "2026-11-02T08:10:00Z"),
    versions: [], relations: [],
  },
  {
    id: "doc-ltm", title: "Luật Thương mại", doc_number: "36/2005/QH11",
    genre: "law", validity_status: "in_force", created_at: "2026-11-02T08:12:00Z",
    current_version: version("v-ltm-1", 1, "luat-thuong-mai-2005.docx", null, "2026-11-02T08:12:00Z"),
    versions: [], relations: [],
  },
  {
    id: "doc-qc", title: "Quy chế nghỉ phép năm 2026", doc_number: "05/2026/QC-NS",
    genre: "policy", validity_status: "in_force", created_at: "2026-10-20T02:30:00Z",
    current_version: version("v-qc-2", 2, "quy-che-nghi-phep-2026.docx", null, "2026-11-05T02:30:00Z"),
    versions: [version("v-qc-1", 1, "quy-che-nghi-phep-2026-du-thao.docx", null, "2026-10-20T02:30:00Z")],
    relations: [
      { relation_type: "replaces", target_number: "04/2025/QC-NS", target_document_id: null, target_title: null },
    ],
  },
  {
    id: "doc-bc", title: "Báo cáo kết quả kinh doanh quý III/2026", doc_number: null,
    genre: "report", validity_status: "unknown", created_at: "2026-11-12T09:45:00Z",
    current_version: version("v-bc-1", 1, "bao-cao-quy-3-2026.pdf", 14, "2026-11-12T09:45:00Z"),
    versions: [], relations: [],
  },
];
for (const d of documents) d.versions = [d.current_version, ...d.versions];

const HD = "Hợp đồng mua bán thiết bị số 12/2026/HĐMB";
const passage = (chunk_id: string, document_id: string, document_title: string, section: string,
  page: number | null, text: string, context: string): PassageOut =>
  ({ chunk_id, document_id, document_title, section, page, text, context });

const HD_ART8 = [
  "Điều 8. Phạt vi phạm và bồi thường thiệt hại",
  "1. Bên vi phạm nghĩa vụ theo Hợp đồng này phải chịu phạt vi phạm và bồi thường thiệt hại theo quy định tại Điều này.",
  "2. Trường hợp Bên B giao hàng chậm so với thời hạn quy định tại Điều 5, Bên B phải trả cho Bên A tiền phạt bằng 0,05% giá trị phần hàng giao chậm cho mỗi ngày chậm giao, nhưng tổng số tiền phạt không vượt quá 8% giá trị phần nghĩa vụ hợp đồng bị vi phạm.",
  "3. Việc trả tiền phạt không miễn trừ nghĩa vụ bồi thường thiệt hại thực tế phát sinh do hành vi vi phạm.",
];
const HD_ART9 = [
  "Điều 9. Bảo hành",
  "1. Bên B bảo hành thiết bị trong thời hạn 24 tháng kể từ ngày hai bên ký biên bản nghiệm thu.",
  "2. Trong thời hạn bảo hành, Bên B sửa chữa hoặc thay thế thiết bị lỗi trong vòng 07 ngày làm việc kể từ ngày nhận được thông báo của Bên A.",
];
const HD_ART3 = [
  "Điều 3. Giá trị hợp đồng",
  "1. Tổng giá trị Hợp đồng là 2.500.000.000 đồng (Hai tỷ năm trăm triệu đồng), đã bao gồm thuế giá trị gia tăng.",
  "2. Giá trị Hợp đồng không thay đổi trong suốt thời gian thực hiện Hợp đồng.",
];
const HD_ART7 = [
  "Điều 7. Thanh toán",
  "1. Bên A thanh toán cho Bên B trong vòng 45 ngày kể từ ngày nhận được hóa đơn hợp lệ.",
  "2. Việc thanh toán được thực hiện bằng chuyển khoản vào tài khoản của Bên B.",
];
const QC_ART3 = [
  "Điều 3. Số ngày nghỉ phép năm",
  "1. Người lao động làm việc đủ 12 tháng được nghỉ phép năm 12 ngày làm việc, hưởng nguyên lương.",
  "2. Người lao động làm việc chưa đủ 12 tháng thì số ngày nghỉ phép năm được tính theo tỷ lệ tương ứng với số tháng làm việc.",
];
const LTM_301 =
  "Mức phạt đối với vi phạm nghĩa vụ hợp đồng hoặc tổng mức phạt đối với nhiều vi phạm do các bên thoả thuận trong hợp đồng, nhưng không quá 8% giá trị phần nghĩa vụ hợp đồng bị vi phạm, trừ trường hợp quy định tại Điều 266 của Luật này.";
const BC_REVENUE = [
  "1. Doanh thu",
  "Doanh thu thuần quý III/2026 đạt 48,6 tỷ đồng, tăng 12% so với cùng kỳ năm trước.",
  "Doanh thu từ thiết bị chiếm 71% tổng doanh thu; phần còn lại đến từ dịch vụ bảo trì.",
];

export const passages: Record<string, PassageOut> = Object.fromEntries(
  [
    passage("c-hd-3-1", "doc-hd", HD, "Điều 3 › Khoản 1", 2, HD_ART3[1], HD_ART3.join("\n")),
    passage("c-hd-7-1", "doc-hd", HD, "Điều 7 › Khoản 1", 3, HD_ART7[1], HD_ART7.join("\n")),
    passage("c-hd-8-2", "doc-hd", HD, "Điều 8 › Khoản 2", 3, HD_ART8[2], HD_ART8.join("\n")),
    passage("c-hd-9-1", "doc-hd", HD, "Điều 9 › Khoản 1", 4, HD_ART9[1], HD_ART9.join("\n")),
    passage("c-hd-9-2", "doc-hd", HD, "Điều 9 › Khoản 2", 4, HD_ART9[2], HD_ART9.join("\n")),
    passage("c-ltm-301", "doc-ltm", "Luật Thương mại 36/2005/QH11", "Chương VII › Điều 301", null, LTM_301,
      `Điều 301. Mức phạt vi phạm\n${LTM_301}`),
    passage("c-qc-3-1", "doc-qc", "Quy chế nghỉ phép năm 2026", "Chương II › Điều 3 › Khoản 1", null, QC_ART3[1],
      QC_ART3.join("\n")),
    passage("c-bc-2-1", "doc-bc", "Báo cáo kết quả kinh doanh quý III/2026", "II. Kết quả kinh doanh › 1. Doanh thu", 3,
      BC_REVENUE[1], BC_REVENUE.join("\n")),
  ].map((p) => [p.chunk_id, p]),
);

/** A citation of a passage, labelled as the answer cites it. */
export function cite(label: string, chunkId: string): CitationOut {
  const p = passages[chunkId];
  const doc = documents.find((d) => d.id === p.document_id)!;
  return {
    label, chunk_id: chunkId, document_id: p.document_id, document_title: p.document_title,
    version_id: doc.current_version.id, section: p.section, page: p.page, verdict: "supported",
  };
}

let nodeSeq = 0;
const node = (level: OutlineNode["level"], number: string | null, title: string | null, page: number | null,
  children: OutlineNode[] = []): OutlineNode => ({ id: `n${++nodeSeq}`, level, number, title, page, children });
const clauses = (n: number, page: number | null) =>
  Array.from({ length: n }, (_, i) => node("clause", `${i + 1}`, null, page));

export const outlines: Record<string, OutlineNode> = {
  "doc-hd": node("document", null, HD, 1, [
    node("article", "1", "Định nghĩa", 1, clauses(3, 1)),
    node("article", "2", "Đối tượng của Hợp đồng", 1, clauses(2, 1)),
    node("article", "3", "Giá trị hợp đồng", 2, clauses(2, 2)),
    node("article", "4", "Chất lượng thiết bị", 2, clauses(2, 2)),
    node("article", "5", "Thời hạn và địa điểm giao hàng", 2, clauses(2, 2)),
    node("article", "6", "Nghiệm thu", 3, clauses(2, 3)),
    node("article", "7", "Thanh toán", 3, clauses(2, 3)),
    node("article", "8", "Phạt vi phạm và bồi thường thiệt hại", 3, clauses(3, 3)),
    node("article", "9", "Bảo hành", 4, clauses(2, 4)),
    node("article", "10", "Bất khả kháng", 4, clauses(2, 4)),
    node("article", "11", "Bảo mật thông tin", 5, clauses(2, 5)),
    node("article", "12", "Điều khoản thi hành", 5, clauses(2, 5)),
  ]),
  "doc-ltm": node("document", null, "Luật Thương mại (trích)", null, [
    node("chapter", "VII", "Chế tài trong thương mại và giải quyết tranh chấp trong thương mại", null, [
      node("article", "300", "Phạt vi phạm", null),
      node("article", "301", "Mức phạt vi phạm", null),
      node("article", "302", "Bồi thường thiệt hại", null, clauses(2, null)),
    ]),
  ]),
  "doc-qc": node("document", null, "Quy chế nghỉ phép năm 2026", null, [
    node("chapter", "I", "Quy định chung", null, [
      node("article", "1", "Phạm vi điều chỉnh", null),
      node("article", "2", "Đối tượng áp dụng", null),
    ]),
    node("chapter", "II", "Nghỉ phép năm", null, [
      node("article", "3", "Số ngày nghỉ phép năm", null, clauses(2, null)),
      node("article", "4", "Thủ tục đăng ký nghỉ phép", null, clauses(3, null)),
    ]),
  ]),
  "doc-bc": node("document", null, "Báo cáo kết quả kinh doanh quý III/2026", 1, [
    node("heading", "I", "Tổng quan", 1),
    node("heading", "II", "Kết quả kinh doanh", 2, [
      node("heading", "1", "Doanh thu", 3),
      node("heading", "2", "Chi phí", 5),
      node("heading", "3", "Lợi nhuận", 7),
    ]),
    node("heading", "III", "Kế hoạch quý IV", 11),
  ]),
};

export const rules: RuleOut[] = [
  {
    id: "contract.penalty_cap", genre: "contract", name: "Mức phạt vi phạm vượt trần",
    condition: { type: "max_percent", near: "phạt vi phạm", max: 8 }, severity: "high",
    basis: "Điều 301 Luật Thương mại 2005: mức phạt không quá 8% giá trị phần nghĩa vụ bị vi phạm",
    enabled: true, updated_at: "2026-11-01T00:00:00Z",
  },
  {
    id: "contract.payment_term", genre: "contract", name: "Thời hạn thanh toán quá dài",
    condition: { type: "max_days", near: "thanh toán", max: 30 }, severity: "medium",
    basis: "Chính sách tài chính nội bộ: thời hạn thanh toán không quá 30 ngày",
    enabled: true, updated_at: "2026-11-01T00:00:00Z",
  },
  {
    id: "contract.dispute_resolution", genre: "contract", name: "Không có điều khoản giải quyết tranh chấp",
    condition: { type: "missing_clause", patterns: ["giải quyết tranh chấp", "trọng tài", "tòa án"] }, severity: "high",
    basis: "Hợp đồng cần quy định cơ quan và cách thức giải quyết tranh chấp", enabled: true,
    updated_at: "2026-11-01T00:00:00Z",
  },
  {
    id: "contract.confidentiality", genre: "contract", name: "Không có điều khoản bảo mật",
    condition: { type: "missing_clause", patterns: ["bảo mật"] }, severity: "medium",
    basis: "Hợp đồng có trao đổi thông tin kỹ thuật cần điều khoản bảo mật", enabled: true,
    updated_at: "2026-11-01T00:00:00Z",
  },
  {
    id: "policy.effective_date", genre: "policy", name: "Thiếu ngày có hiệu lực",
    condition: { type: "required_metadata", field: "effective_date" }, severity: "medium",
    basis: "Quy chế phải ghi rõ ngày có hiệu lực", enabled: true, updated_at: "2026-11-01T00:00:00Z",
  },
  {
    id: "report.totals", genre: "report", name: "Dòng tổng không khớp",
    condition: { type: "sum_mismatch", table_pattern: "Tổng cộng" }, severity: "high",
    basis: "Dòng tổng của bảng phải bằng tổng các dòng thành phần", enabled: false,
    updated_at: "2026-11-01T00:00:00Z",
  },
];

/** The latest review of each document (BR17: a new run replaces the previous one). */
export const reviews: Record<string, ReviewRunOut> = {};

export const conversations: ConversationOut[] = [
  { id: "c-1", title: "Phạt chậm giao hàng", pinned: true, created_at: "2026-11-18T03:00:00Z", updated_at: "2026-11-18T03:04:00Z" },
  { id: "c-2", title: "Thời hạn bảo hành thiết bị", pinned: false, created_at: "2026-11-17T07:20:00Z", updated_at: "2026-11-17T07:26:00Z" },
  { id: "c-3", title: "Số ngày nghỉ phép năm", pinned: false, created_at: "2026-11-12T10:00:00Z", updated_at: "2026-11-12T10:02:00Z" },
];

/** Turns of each conversation, oldest first. */
export const turns: Record<string, TurnOut[]> = {};
