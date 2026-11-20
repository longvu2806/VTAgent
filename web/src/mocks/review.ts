// Mock review runs: the findings each enabled rule would produce on the sample documents.
import type { FindingOut, ReviewRunOut, RuleOut } from "@/api/types";
import { documents, reviews, rules } from "./fixtures";

// What each rule finds on the sample documents; rules not listed find nothing there.
const SAMPLE_FINDINGS: Record<string, Record<string, Omit<FindingOut, "rule_id" | "rule_name" | "severity" | "basis">>> = {
  "doc-hd": {
    "contract.payment_term": {
      description: "Hợp đồng cho Bên A 45 ngày để thanh toán, dài hơn mức tối đa 30 ngày.",
      value: "45 ngày", passages: ["c-hd-7-1"],
    },
    "contract.dispute_resolution": {
      description: "Không tìm thấy điều khoản nào quy định cách giải quyết tranh chấp, trọng tài hay tòa án.",
      value: null, passages: [],
    },
  },
};

const RUN_MS = 2500;

export function startReview(documentId: string): ReviewRunOut {
  const document = documents.find((d) => d.id === documentId)!;
  const run: ReviewRunOut = {
    id: crypto.randomUUID(), document_id: documentId, version_id: document.current_version.id,
    status: "running", started_at: new Date().toISOString(), findings: [],
  };
  reviews[documentId] = run; // a new run replaces the previous one (BR17)
  setTimeout(() => {
    const applicable = rules.filter((r: RuleOut) => r.enabled && r.genre === document.genre);
    run.findings = applicable.flatMap((r) => {
      const found = SAMPLE_FINDINGS[documentId]?.[r.id];
      return found ? [{ rule_id: r.id, rule_name: r.name, severity: r.severity, basis: r.basis, ...found }] : [];
    });
    run.status = "done";
  }, RUN_MS);
  return run;
}
