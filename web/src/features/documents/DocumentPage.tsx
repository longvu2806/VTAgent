// One document: metadata, version history and relations, its recognised structure, and
// the rule-based review.
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { FileUpIcon, MessageSquareTextIcon, Trash2Icon } from "lucide-react";
import { useRef, useState } from "react";
import { useDocument } from "@/api/client";
import type { DocumentDetail } from "@/api/types";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ReviewPanel } from "@/features/review/ReviewPanel";
import { formatDate, GENRE, RELATION, VALIDITY } from "@/lib/labels";
import { DeleteDocumentDialog, titleOf, useAskAbout } from "./actions";
import { Outline } from "./Outline";
import { UploadChip } from "./UploadChip";
import { ACCEPTED, uploadVersion, useUploads } from "./uploads";

export function DocumentPage() {
  const { documentId } = useParams({ from: "/documents/$documentId" });
  const { data: document, isLoading, isError } = useDocument(documentId);

  return (
    <ScrollArea className="h-full">
      <div className="mx-auto flex max-w-4xl flex-col gap-6 px-8 py-8">
        <nav aria-label="Vị trí" className="text-sm text-muted-foreground">
          <Link to="/documents" className="hover:text-foreground">
            Tài liệu
          </Link>
          <span className="mx-1.5">/</span>
          <span className="text-foreground">{document ? titleOf(document) : "…"}</span>
        </nav>
        {isLoading && <Skeleton className="h-24 w-full" />}
        {isError && <p className="text-muted-foreground">Không tìm thấy tài liệu này. Có thể nó đã bị xóa.</p>}
        {document && <Detail document={document} />}
      </div>
    </ScrollArea>
  );
}

function Detail({ document: d }: { document: DocumentDetail }) {
  const askAbout = useAskAbout();
  const navigate = useNavigate();
  const uploads = useUploads((s) => s.items);
  const [deleting, setDeleting] = useState(false);
  const picker = useRef<HTMLInputElement>(null);
  const v = d.current_version;

  return (
    <>
      <header className="flex flex-col gap-1.5">
        <h1 className="text-2xl font-semibold tracking-tight text-balance text-ink">{titleOf(d)}</h1>
        <p className="text-muted-foreground">
          {[GENRE[d.genre], d.doc_number && `Số ${d.doc_number}`, VALIDITY[d.validity_status]].filter(Boolean).join(" · ")}
        </p>
        <div className="mt-2 flex flex-wrap gap-2">
          <Button onClick={() => askAbout(d.id)}>
            <MessageSquareTextIcon /> Hỏi về tài liệu này
          </Button>
          <input
            ref={picker}
            type="file"
            hidden
            accept={ACCEPTED}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) uploadVersion(d.id, file);
              e.target.value = "";
            }}
          />
          <Button variant="outline" onClick={() => picker.current?.click()}>
            <FileUpIcon /> Tải phiên bản mới
          </Button>
          <Button variant="ghost" size="icon" aria-label="Xóa tài liệu" onClick={() => setDeleting(true)}>
            <Trash2Icon />
          </Button>
        </div>
      </header>
      {uploads.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {uploads.map((u) => (
            <UploadChip key={u.jobId} upload={u} />
          ))}
        </div>
      )}
      <Tabs defaultValue="overview" className="gap-5">
        <TabsList variant="line">
          <TabsTrigger value="overview">Tổng quan</TabsTrigger>
          <TabsTrigger value="outline">Cấu trúc</TabsTrigger>
          <TabsTrigger value="review">Rà soát</TabsTrigger>
        </TabsList>
        <TabsContent value="overview" className="flex flex-col gap-8 text-[0.95rem]">
          <dl className="grid grid-cols-[max-content_1fr] gap-x-8 gap-y-2">
            <dt className="text-muted-foreground">Tệp hiện hành</dt>
            <dd>{v.file_name}</dd>
            <dt className="text-muted-foreground">Số trang</dt>
            <dd>{v.pages ?? "Không áp dụng"}</dd>
            <dt className="text-muted-foreground">Nạp ngày</dt>
            <dd>{formatDate(v.ingested_at)}</dd>
          </dl>
          <section className="flex flex-col gap-2">
            <h2 className="font-semibold">Phiên bản</h2>
            <ol className="flex flex-col divide-y rounded-lg border">
              {d.versions.map((ver) => (
                <li key={ver.id} className="flex flex-wrap items-baseline gap-x-3 px-4 py-2.5">
                  <span className="font-medium tabular-nums">Phiên bản {ver.seq}</span>
                  {ver.id === v.id && <span className="text-xs font-medium text-ink">Hiện hành</span>}
                  <span className="text-muted-foreground">{ver.file_name}</span>
                  <span className="ml-auto text-sm text-muted-foreground tabular-nums">{formatDate(ver.ingested_at)}</span>
                </li>
              ))}
            </ol>
          </section>
          <section className="flex flex-col gap-2">
            <h2 className="font-semibold">Quan hệ với văn bản khác</h2>
            {d.relations.length === 0 ? (
              <p className="text-muted-foreground">Không nhận diện được quan hệ nào.</p>
            ) : (
              <ul className="flex flex-col gap-1">
                {d.relations.map((r) => (
                  <li key={`${r.relation_type}-${r.target_number}`}>
                    {RELATION[r.relation_type]}{" "}
                    {r.target_document_id ? (
                      <Link
                        to="/documents/$documentId"
                        params={{ documentId: r.target_document_id }}
                        className="text-ink underline underline-offset-4"
                      >
                        {r.target_title ?? r.target_number}
                      </Link>
                    ) : (
                      <>
                        văn bản số {r.target_number} <span className="text-muted-foreground">(chưa nạp)</span>
                      </>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </TabsContent>
        <TabsContent value="outline" className="text-[0.95rem]">
          <Outline documentId={d.id} />
        </TabsContent>
        <TabsContent value="review" className="text-[0.95rem]">
          <ReviewPanel document={d} />
        </TabsContent>
      </Tabs>
      <DeleteDocumentDialog
        document={deleting ? d : null}
        onClose={() => setDeleting(false)}
        onDeleted={() => navigate({ to: "/documents" })}
      />
    </>
  );
}
