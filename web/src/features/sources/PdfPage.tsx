// The cited page as it looks in the original PDF, with the cited lines highlighted in the
// text layer and scrolled into view.
import { useEffect, useMemo, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/TextLayer.css";
import { useDocumentFile } from "@/api/client";
import { Skeleton } from "@/components/ui/skeleton";
import { quoteItems } from "@/lib/pdfQuote";

pdfjs.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();

const escape = (s: string) => s.replace(/[&<>"]/g, (c) => `&#${c.charCodeAt(0)};`);

export function PdfPage({ documentId, page, quote }: { documentId: string; page: number; quote: string }) {
  const { data: file, isError } = useDocumentFile(documentId);
  const box = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState<number>();
  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => setWidth(Math.floor(entry.contentRect.width)));
    observer.observe(box.current!);
    return () => observer.disconnect();
  }, []);

  // The page's text is kept so switching between quotes on the same page re-highlights.
  const [items, setItems] = useState<readonly object[]>([]);
  const hits = useMemo(() => quoteItems(items, quote), [items, quote]);
  const highlight = useMemo(
    () =>
      ({ str, itemIndex }: { str: string; itemIndex: number }) =>
        hits.has(itemIndex) ? `<mark class="pdf-hit">${escape(str)}</mark>` : escape(str),
    [hits],
  );

  const loading = <Skeleton className="aspect-[1/1.414] w-full" />;
  return (
    <div ref={box} className="w-full">
      {isError ? (
        <p className="text-sm text-muted-foreground">Không mở được tệp gốc của tài liệu này.</p>
      ) : !file || !width ? (
        loading
      ) : (
        <Document file={file} loading={loading} error={<p className="text-sm text-muted-foreground">Không đọc được tệp PDF.</p>}>
          <Page
            pageNumber={page}
            width={width}
            loading={loading}
            renderAnnotationLayer={false}
            onGetTextSuccess={(text) => setItems(text.items)}
            customTextRenderer={highlight}
            onRenderTextLayerSuccess={() => box.current?.querySelector("mark")?.scrollIntoView({ block: "center" })}
            className="overflow-hidden rounded-sm border shadow-[0_8px_24px_-16px_rgb(28_46_74/0.35)]"
          />
        </Document>
      )}
    </div>
  );
}
