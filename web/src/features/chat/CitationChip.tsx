import type { CitationOut } from "@/api/types";
import { usePassage } from "@/api/client";
import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card";
import { useUi } from "@/stores/ui";

/** An inline citation: hover shows the passage, click opens it on the source sheet (FR-19, FR-20). */
export function CitationChip({ citation, all }: { citation: CitationOut; all: CitationOut[] }) {
  const openSource = useUi((s) => s.openSource);
  const active = useUi(
    (s) => s.activeLabel === citation.label && s.sources.some((r) => r.label === citation.label && r.chunkId === citation.chunk_id),
  );
  const open = () => openSource(all.map((c) => ({ label: c.label, chunkId: c.chunk_id })), citation.label);
  return (
    <HoverCard>
      <HoverCardTrigger
        delay={250}
        render={
          <button
            onClick={open}
            aria-label={`Nguồn ${citation.label.slice(1)}: ${citation.document_title}, ${citation.section}`}
            className="mx-0.5 inline-flex min-w-[1.35rem] -translate-y-px items-center justify-center rounded-[5px] bg-ink/10 px-1 align-baseline text-[0.72rem] font-semibold leading-[1.35] text-ink tabular-nums transition-colors hover:bg-ink hover:text-primary-foreground data-[active=true]:bg-ink data-[active=true]:text-primary-foreground"
            data-active={active}
          />
        }
      >
        {citation.label.slice(1)}
      </HoverCardTrigger>
      <HoverCardContent side="top" className="w-80 p-0">
        <Preview citation={citation} />
      </HoverCardContent>
    </HoverCard>
  );
}

function Preview({ citation }: { citation: CitationOut }) {
  const { data } = usePassage(citation.chunk_id);
  return (
    <div className="flex flex-col gap-2 p-3">
      <div className="text-xs text-muted-foreground">
        <div className="font-medium text-foreground">{citation.document_title}</div>
        {citation.section}
        {citation.page !== null && `, trang ${citation.page}`}
      </div>
      <p className="line-clamp-5 font-serif text-[0.85rem] leading-relaxed">{data?.text ?? "Đang tải đoạn trích…"}</p>
    </div>
  );
}
