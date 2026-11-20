// The source sheet: the cited passage read in its context, set in serif on paper with
// the cited words highlighted, or the original PDF page, so the user can check the answer
// against the source.
import { XIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { useDocument, usePassage } from "@/api/client";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useUi } from "@/stores/ui";
import { PdfPage } from "./PdfPage";

function Highlighted({ context, quote }: { context: string; quote: string }) {
  const at = context.indexOf(quote);
  const paragraphs = (text: string) =>
    text.split("\n").map((line, i, all) => (
      <span key={i}>
        {line}
        {i < all.length - 1 && <br />}
      </span>
    ));
  if (at < 0) return <>{paragraphs(context)}</>;
  return (
    <>
      {paragraphs(context.slice(0, at))}
      <mark className="rounded-[2px] bg-highlight px-0.5 text-inherit [box-decoration-break:clone]">{quote}</mark>
      {paragraphs(context.slice(at + quote.length))}
    </>
  );
}

export function SourcePanel() {
  const { sources, activeLabel, openSource, closeSource } = useUi();
  const active = sources.find((s) => s.label === activeLabel);
  const { data: passage } = usePassage(active?.chunkId);
  const { data: document } = useDocument(passage?.document_id);
  const [view, setView] = useState<"text" | "page">("text");

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !e.defaultPrevented) closeSource();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [closeSource]);

  if (!active) return null;
  const hasPage = passage?.page != null && document?.current_version.file_ext.endsWith("pdf") === true;
  const path = passage?.section.split("›").map((s) => s.trim()) ?? [];

  return (
    <aside className="flex h-full flex-col bg-muted/60" aria-label="Đoạn gốc">
      <div className="flex items-center gap-1 border-b px-3 py-2">
        <nav className="flex gap-1" aria-label="Các nguồn được trích">
          {sources.map((s) => (
            <button
              key={s.label}
              onClick={() => openSource(sources, s.label)}
              aria-current={s.label === activeLabel}
              aria-label={`Nguồn ${s.label.slice(1)}`}
              className="min-w-7 rounded-md px-2 py-1 text-sm font-medium text-muted-foreground tabular-nums hover:bg-accent aria-[current=true]:bg-ink aria-[current=true]:text-primary-foreground"
            >
              {s.label.slice(1)}
            </button>
          ))}
        </nav>
        <Button variant="ghost" size="icon" className="ml-auto" aria-label="Đóng đoạn gốc (Esc)" onClick={closeSource}>
          <XIcon />
        </Button>
      </div>
      <ScrollArea className="min-h-0 flex-1">
        <div className="flex flex-col gap-4 p-5">
          {passage ? (
            <header className="flex flex-col gap-1.5">
              <h2 className="text-base font-semibold leading-snug text-ink">{passage.document_title}</h2>
              <p className="flex flex-wrap items-center gap-x-1.5 text-sm text-muted-foreground">
                {path.map((p, i) => (
                  <span key={i} className={i === path.length - 1 ? "font-medium text-foreground" : undefined}>
                    {i > 0 && <span className="mr-1.5 text-border">/</span>}
                    {p}
                  </span>
                ))}
                {passage.page !== null && <span className="ml-2">trang {passage.page}</span>}
              </p>
            </header>
          ) : (
            <Skeleton className="h-10 w-2/3" />
          )}
          {hasPage && (
            <Tabs value={view} onValueChange={(v) => setView(v as "text" | "page")}>
              <TabsList>
                <TabsTrigger value="text">Đoạn trích</TabsTrigger>
                <TabsTrigger value="page">Trang gốc</TabsTrigger>
              </TabsList>
            </Tabs>
          )}
          {hasPage && view === "page" ? (
            <PdfPage documentId={passage.document_id} page={passage.page!} quote={passage.text} />
          ) : (
            <article className="rounded-sm border bg-paper px-7 py-8 font-serif text-[0.98rem] leading-[1.85] shadow-[0_1px_0_var(--border),0_8px_24px_-16px_rgb(28_46_74/0.35)]">
              {passage ? (
                <Highlighted context={passage.context} quote={passage.text} />
              ) : (
                <div className="flex flex-col gap-3">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-5/6" />
                </div>
              )}
            </article>
          )}
        </div>
      </ScrollArea>
    </aside>
  );
}
