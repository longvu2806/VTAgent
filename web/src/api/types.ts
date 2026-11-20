// REST payloads of the VTAgent API (SDD §10.1). Hand-written until the FastAPI
// backend exists; then replaced by types generated from its OpenAPI schema.

export type Genre = "law" | "contract" | "policy" | "report" | "technical" | "unknown";
export type ValidityStatus = "in_force" | "partly_expired" | "expired" | "unknown";

export interface VersionOut {
  id: string;
  seq: number;
  file_name: string;
  file_ext: string;
  pages: number | null;
  status: "processing" | "ready" | "failed";
  ingested_at: string;
}

export interface DocumentOut {
  id: string;
  title: string | null;
  doc_number: string | null;
  genre: Genre;
  validity_status: ValidityStatus;
  current_version: VersionOut;
  created_at: string;
}

export interface CitationOut {
  label: string; // "S1"
  chunk_id: string;
  document_id: string;
  document_title: string;
  version_id: string;
  section: string; // "Chương II › Điều 5 › Khoản 2"
  page: number | null;
  verdict: "supported" | "unsupported" | "unchecked";
}

export type TurnStatus = "processing" | "answered" | "partial" | "not_found" | "failed";

export interface SentenceWarning {
  sentence_index: number;
  reason: string;
}

export interface TurnOut {
  id: string;
  conversation_id: string;
  question: string;
  status: TurnStatus;
  answer: string | null;
  missing: string | null;
  citations: CitationOut[];
  warnings: SentenceWarning[];
  scope: string[];
  latency_ms: number | null;
  created_at: string;
}

export interface ConversationOut {
  id: string;
  title: string | null;
  pinned: boolean;
  created_at: string;
  updated_at: string;
}

export type JobStage = "validating" | "parsing" | "structuring" | "chunking" | "embedding" | "indexing";

export interface JobOut {
  id: string;
  file_name: string;
  status: "queued" | "running" | "done" | "duplicate" | "failed";
  stage: JobStage | null;
  progress: number | null;
  document_id: string | null;
  error: { code: string; detail: string } | null;
}

export interface ConversationDetail extends ConversationOut {
  turns: TurnOut[];
}

export interface PassageOut {
  chunk_id: string;
  document_id: string;
  document_title: string;
  section: string;
  page: number | null;
  text: string; // the cited chunk
  context: string; // its parent, to read the chunk in context (FR-20)
}

export type RelationType = "amends" | "supplements" | "replaces" | "repeals" | "guides";

export interface RelationOut {
  relation_type: RelationType;
  target_number: string;
  target_document_id: string | null; // null when the target is not loaded
  target_title: string | null;
}

export interface DocumentDetail extends DocumentOut {
  versions: VersionOut[];
  relations: RelationOut[];
}

export interface OutlineNode {
  id: string;
  level: "document" | "part" | "chapter" | "section" | "article" | "clause" | "point" | "appendix" | "heading";
  number: string | null;
  title: string | null;
  page: number | null;
  children: OutlineNode[];
}

export type Severity = "high" | "medium" | "low";

/** Closed set of rule conditions, each evaluated deterministically (SDD §7.8). */
export type RuleCondition =
  | { type: "missing_clause"; patterns: string[] }
  | { type: "required_metadata"; field: string }
  | { type: "max_percent" | "max_amount" | "max_days"; near: string; max: number }
  | { type: "sum_mismatch"; table_pattern: string };

export interface RuleIn {
  genre: Genre;
  name: string;
  condition: RuleCondition;
  severity: Severity;
  basis: string;
  enabled: boolean;
}

export interface RuleOut extends RuleIn {
  id: string;
  updated_at: string;
}

export interface FindingOut {
  rule_id: string;
  rule_name: string;
  severity: Severity;
  description: string;
  basis: string;
  value: string | null;
  passages: string[]; // chunk ids; empty when the finding is a missing clause
}

export interface ReviewRunOut {
  id: string;
  document_id: string;
  version_id: string;
  status: "running" | "done" | "failed";
  started_at: string;
  findings: FindingOut[];
}
