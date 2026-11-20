// Mock document ingestion: uploads become jobs whose progress streams over SSE (SDD §9.3).
// The file name decides the outcome so every path can be tried: a non-PDF/DOCX file is
// rejected, a name containing "scan" has no text layer, a known name is a duplicate.
import type { DocumentDetail, Genre, JobOut, JobStage } from "@/api/types";
import { documents, outlines } from "./fixtures";

const STAGES: JobStage[] = ["validating", "parsing", "structuring", "chunking", "embedding", "indexing"];

interface MockJob extends JobOut {
  pages: number;
  newVersionOf: string | null; // document id, for POST /documents/{id}/versions
}

const jobs = new Map<string, MockJob>();

export type JobEvent =
  | { event: "stage"; data: { stage: JobStage; progress: number } }
  | { event: "done"; data: { document_id: string; genre: Genre; duplicate: boolean } }
  | { event: "failed"; data: { code: string; message: string } };

function guessGenre(name: string): Genre {
  const n = name.toLowerCase();
  if (/hop-dong|hợp đồng|hop_dong|contract/.test(n)) return "contract";
  if (/luat|luật|nghi-dinh|nghị định|thong-tu|law/.test(n)) return "law";
  if (/quy-che|quy-trinh|quy chế|quy trình|policy/.test(n)) return "policy";
  if (/bao-cao|báo cáo|report/.test(n)) return "report";
  return "unknown";
}

export function createJob(file: File, newVersionOf: string | null = null): JobOut {
  const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  const job: MockJob = {
    id: crypto.randomUUID(), file_name: file.name, status: "queued", stage: null, progress: 0,
    document_id: null, error: null, pages: 1 + (file.size % 40), newVersionOf,
  };
  const existing = documents.find((d) => d.versions.some((v) => v.file_name === file.name));
  if (ext !== ".pdf" && ext !== ".docx") {
    job.status = "failed";
    job.error = { code: "unsupported_format", detail: "Chỉ nhận tệp PDF hoặc DOCX." };
  } else if (existing) {
    job.status = "duplicate";
    job.document_id = existing.id;
  }
  jobs.set(job.id, job);
  const { pages: _p, newVersionOf: _n, ...out } = job;
  return out;
}

/** The events of a job, in order, with the delay before each. */
export function jobEvents(id: string): { event: JobEvent; delay: number }[] {
  const job = jobs.get(id);
  const fail = (code: string, message: string, delay = 200) => [{ event: { event: "failed" as const, data: { code, message } }, delay }];
  if (!job) return fail("not_found", "Không có tác vụ.", 0);
  if (job.status === "failed") return fail(job.error!.code, job.error!.detail);
  if (job.status === "duplicate") {
    const genre = documents.find((d) => d.id === job.document_id)!.genre;
    return [{ event: { event: "done", data: { document_id: job.document_id!, genre, duplicate: true } }, delay: 300 }];
  }
  const events: { event: JobEvent; delay: number }[] = STAGES.map((stage, i) => ({
    event: { event: "stage", data: { stage, progress: i / STAGES.length } }, delay: 500,
  }));
  if (/scan/i.test(job.file_name)) return [...events.slice(0, 2), ...fail("no_text_layer", "Tệp là ảnh quét, không có lớp văn bản.", 700)];
  const document = job.newVersionOf ? addVersion(job) : addDocument(job);
  events.push({ event: { event: "done", data: { document_id: document.id, genre: document.genre, duplicate: false } }, delay: 600 });
  return events;
}

function newVersion(job: MockJob, seq: number) {
  const ext = job.file_name.slice(job.file_name.lastIndexOf(".")).toLowerCase();
  return {
    id: `v-${job.id.slice(0, 8)}`, seq, file_name: job.file_name, file_ext: ext,
    pages: ext === ".pdf" ? job.pages : null, status: "ready" as const, ingested_at: new Date().toISOString(),
  };
}

function addDocument(job: MockJob): DocumentDetail {
  const current = newVersion(job, 1);
  const title = job.file_name.replace(/\.[^.]+$/, "").replace(/[-_]+/g, " ");
  const document: DocumentDetail = {
    id: `doc-${job.id.slice(0, 8)}`, title, doc_number: null, genre: guessGenre(job.file_name),
    validity_status: "unknown", created_at: current.ingested_at, current_version: current, versions: [current],
    relations: [],
  };
  outlines[document.id] = { id: `${document.id}-root`, level: "document", number: null, title, page: 1, children: [] };
  documents.unshift(document);
  return document;
}

function addVersion(job: MockJob): DocumentDetail {
  const document = documents.find((d) => d.id === job.newVersionOf)!;
  const current = newVersion(job, document.current_version.seq + 1);
  document.current_version = current;
  document.versions = [current, ...document.versions];
  return document;
}
