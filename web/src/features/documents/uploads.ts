// Uploading documents: one ingest job per file, followed over SSE (SDD §9.3). A new
// document joins the question scope, so the next question is about the file just added.
import { toast } from "sonner";
import { create } from "zustand";
import { API } from "@/api/client";
import type { JobOut, JobStage } from "@/api/types";
import { queryClient } from "@/lib/query";
import { useUi } from "@/stores/ui";

export interface Upload {
  jobId: string;
  fileName: string;
  stage: JobStage | null;
  progress: number;
  error: string | null;
}

interface UploadState {
  items: Upload[];
  put: (upload: Upload) => void;
  patch: (jobId: string, change: Partial<Upload>) => void;
  remove: (jobId: string) => void;
}

export const useUploads = create<UploadState>((set) => ({
  items: [],
  put: (upload) => set((s) => ({ items: [...s.items, upload] })),
  patch: (jobId, change) => set((s) => ({ items: s.items.map((u) => (u.jobId === jobId ? { ...u, ...change } : u)) })),
  remove: (jobId) => set((s) => ({ items: s.items.filter((u) => u.jobId !== jobId) })),
}));

export const STAGE_TEXT: Record<JobStage, string> = {
  validating: "Đang kiểm tra",
  parsing: "Đang đọc nội dung",
  structuring: "Đang nhận diện cấu trúc",
  chunking: "Đang chia đoạn",
  embedding: "Đang lập chỉ mục",
  indexing: "Đang lưu chỉ mục",
};

export const ACCEPTED = ".pdf,.docx";

function follow(job: JobOut, newVersion: boolean) {
  const { put, patch, remove } = useUploads.getState();
  put({ jobId: job.id, fileName: job.file_name, stage: null, progress: 0, error: null });
  const events = new EventSource(`${API}/jobs/${job.id}/events`);
  events.addEventListener("stage", (e) => {
    const { stage, progress } = JSON.parse(e.data);
    patch(job.id, { stage, progress });
  });
  events.addEventListener("done", (e) => {
    const { document_id, duplicate } = JSON.parse(e.data);
    events.close();
    remove(job.id);
    queryClient.invalidateQueries({ queryKey: ["documents"] });
    if (newVersion) return toast.success(`Đã nạp phiên bản mới từ ${job.file_name}`);
    useUi.getState().addScope(document_id);
    toast.success(duplicate ? `${job.file_name} đã có trong kho, dùng bản đã nạp` : `Đã nạp ${job.file_name}`);
  });
  events.addEventListener("failed", (e) => {
    const { message } = JSON.parse(e.data);
    events.close();
    patch(job.id, { error: message });
  });
  events.onerror = () => {
    events.close();
    patch(job.id, { error: "Mất kết nối khi theo dõi tiến trình nạp." });
  };
}

async function post(path: string, form: FormData): Promise<unknown> {
  const res = await fetch(`${API}${path}`, { method: "POST", body: form, headers: { "x-vtagent": "1" } });
  if (!res.ok) {
    const problem = await res.json().catch(() => ({}));
    toast.error(problem.detail ?? "Không tải được tệp lên.");
    return null;
  }
  return res.json();
}

export async function uploadFiles(files: File[]) {
  if (!files.length) return;
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  const accepted = (await post("/documents", form)) as { jobs: JobOut[] } | null;
  accepted?.jobs.forEach((job) => follow(job, false));
}

/** A new version of a document (UC02): the previous one stays in its history. */
export async function uploadVersion(documentId: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  const job = (await post(`/documents/${documentId}/versions`, form)) as JobOut | null;
  if (job) follow(job, true);
}
