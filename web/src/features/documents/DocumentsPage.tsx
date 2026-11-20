// The document store (UC01–UC03): every loaded document, uploads by button or drag and
// drop, and per-document actions.
import { Link, useNavigate } from "@tanstack/react-router";
import { EllipsisIcon, FileTextIcon, FileUpIcon, MessageSquareTextIcon, Trash2Icon } from "lucide-react";
import { useRef, useState } from "react";
import { useDropzone } from "react-dropzone";
import { useDocuments } from "@/api/client";
import type { DocumentOut } from "@/api/types";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate, GENRE, VALIDITY } from "@/lib/labels";
import { DeleteDocumentDialog, titleOf, useAskAbout } from "./actions";
import { UploadChip } from "./UploadChip";
import { ACCEPTED, uploadFiles, useUploads } from "./uploads";

export function DocumentsPage() {
  const { data: documents, isLoading } = useDocuments();
  const uploads = useUploads((s) => s.items);
  const [deleting, setDeleting] = useState<DocumentOut | null>(null);
  const picker = useRef<HTMLInputElement>(null);
  // Drop anywhere on the page; the server says why a file is refused (FR-02).
  const { getRootProps, isDragActive } = useDropzone({ onDrop: uploadFiles, noClick: true, noKeyboard: true });

  return (
    <div {...getRootProps({ className: "relative h-full outline-none" })}>
      <ScrollArea className="h-full">
        <div className="mx-auto flex max-w-5xl flex-col gap-6 px-8 py-8">
          <header className="flex flex-wrap items-end gap-4">
            <div className="flex flex-1 flex-col gap-1">
              <h1 className="text-2xl font-semibold tracking-tight text-ink">Tài liệu</h1>
              <p className="text-muted-foreground">
                {documents?.length ?? 0} tài liệu đã nạp. Kéo thả tệp PDF hoặc DOCX vào trang này để nạp thêm.
              </p>
            </div>
            <input
              ref={picker}
              type="file"
              multiple
              hidden
              accept={ACCEPTED}
              onChange={(e) => {
                uploadFiles(Array.from(e.target.files ?? []));
                e.target.value = "";
              }}
            />
            <Button onClick={() => picker.current?.click()}>
              <FileUpIcon /> Tải tài liệu lên
            </Button>
          </header>
          {uploads.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {uploads.map((u) => (
                <UploadChip key={u.jobId} upload={u} />
              ))}
            </div>
          )}
          {isLoading ? (
            <div className="flex flex-col gap-2">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            </div>
          ) : documents?.length ? (
            <DocumentTable documents={documents} onDelete={setDeleting} />
          ) : (
            <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed px-6 py-16 text-center">
              <FileTextIcon className="size-8 text-muted-foreground" />
              <p className="font-medium">Chưa có tài liệu nào</p>
              <p className="max-w-md text-sm text-muted-foreground">
                Nạp hợp đồng, văn bản pháp luật, quy chế hay báo cáo để bắt đầu hỏi đáp. Tài liệu chỉ được xử lý trên
                máy này.
              </p>
            </div>
          )}
        </div>
      </ScrollArea>
      {isDragActive && (
        <div className="absolute inset-3 flex items-center justify-center rounded-xl border-2 border-dashed border-ink/50 bg-background/90 text-lg font-medium text-ink">
          Thả tệp để nạp vào kho tài liệu
        </div>
      )}
      <DeleteDocumentDialog document={deleting} onClose={() => setDeleting(null)} />
    </div>
  );
}

function DocumentTable({ documents, onDelete }: { documents: DocumentOut[]; onDelete: (d: DocumentOut) => void }) {
  const navigate = useNavigate();
  const askAbout = useAskAbout();
  return (
    <table className="w-full text-sm">
      <thead className="border-b text-left text-xs text-muted-foreground">
        <tr>
          <th className="py-2 pr-4 font-medium">Tài liệu</th>
          <th className="py-2 pr-4 font-medium">Thể loại</th>
          <th className="py-2 pr-4 font-medium">Hiệu lực</th>
          <th className="py-2 pr-4 font-medium">Phiên bản</th>
          <th className="py-2 pr-4 font-medium">Nạp ngày</th>
          <th className="w-10" aria-label="Thao tác" />
        </tr>
      </thead>
      <tbody>
        {documents.map((d) => (
          <tr key={d.id} className="border-b last:border-0 hover:bg-muted/50">
            <td className="py-3 pr-4">
              <Link
                to="/documents/$documentId"
                params={{ documentId: d.id }}
                className="font-medium text-ink underline-offset-4 hover:underline"
              >
                {titleOf(d)}
              </Link>
              <div className="text-xs text-muted-foreground">
                {[d.doc_number, d.current_version.file_name].filter(Boolean).join(" · ")}
              </div>
            </td>
            <td className="py-3 pr-4">{GENRE[d.genre]}</td>
            <td className="py-3 pr-4 text-muted-foreground">{VALIDITY[d.validity_status]}</td>
            <td className="py-3 pr-4 tabular-nums">
              {d.current_version.seq}
              {d.current_version.pages !== null && (
                <span className="text-muted-foreground"> · {d.current_version.pages} trang</span>
              )}
            </td>
            <td className="py-3 pr-4 text-muted-foreground tabular-nums">{formatDate(d.current_version.ingested_at)}</td>
            <td className="py-3">
              <DropdownMenu>
                <DropdownMenuTrigger
                  render={<Button variant="ghost" size="icon-sm" aria-label={`Tùy chọn cho ${titleOf(d)}`} />}
                >
                  <EllipsisIcon />
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-52">
                  <DropdownMenuItem onClick={() => askAbout(d.id)}>
                    <MessageSquareTextIcon /> Hỏi về tài liệu này
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onClick={() => navigate({ to: "/documents/$documentId", params: { documentId: d.id } })}
                  >
                    <FileTextIcon /> Xem chi tiết
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem variant="destructive" onClick={() => onDelete(d)}>
                    <Trash2Icon /> Xóa
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
