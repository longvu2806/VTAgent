import { FileTextIcon, TriangleAlertIcon, XIcon } from "lucide-react";
import { STAGE_TEXT, type Upload, useUploads } from "./uploads";

/** A file being ingested: its stage and progress, or why it was rejected (FR-02, FR-07). */
export function UploadChip({ upload: u }: { upload: Upload }) {
  const remove = useUploads((s) => s.remove);
  if (u.error) {
    return (
      <span className="flex max-w-80 items-center gap-1.5 rounded-md border border-destructive/40 bg-destructive/5 py-1 pr-1 pl-2 text-xs text-destructive">
        <TriangleAlertIcon className="size-3.5 shrink-0" />
        <span className="truncate" title={`${u.fileName}: ${u.error}`}>
          {u.fileName}: {u.error}
        </span>
        <button type="button" aria-label={`Đóng thông báo lỗi của ${u.fileName}`} onClick={() => remove(u.jobId)}>
          <XIcon className="size-3.5" />
        </button>
      </span>
    );
  }
  return (
    <span className="flex max-w-80 items-center gap-2 rounded-md border bg-card py-1 pr-2 pl-2 text-xs" aria-live="polite">
      <FileTextIcon className="size-3.5 shrink-0 text-muted-foreground" />
      <span className="truncate">{u.fileName}</span>
      <span className="shrink-0 text-muted-foreground">{u.stage ? STAGE_TEXT[u.stage] : "Đang tải lên"}</span>
      <span className="h-1 w-12 shrink-0 overflow-hidden rounded-full bg-muted">
        <span className="block h-full rounded-full bg-ink transition-[width] duration-300" style={{ width: `${Math.round(u.progress * 100)}%` }} />
      </span>
    </span>
  );
}
