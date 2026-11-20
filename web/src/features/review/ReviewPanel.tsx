// Rule-based review of one document (UC08, FR-26): run it, follow the run, read the
// findings by severity with the passages behind them, and export the result.
import { Link } from "@tanstack/react-router";
import { DownloadIcon, FileSearchIcon, ListChecksIcon, RotateCcwIcon } from "lucide-react";
import { toast } from "sonner";
import { download, useLatestReview, useRules, useStartReview } from "@/api/client";
import type { DocumentOut, FindingOut, Severity } from "@/api/types";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { formatTime, GENRE } from "@/lib/labels";
import { useUi } from "@/stores/ui";
import { SeverityBadge } from "./SeverityBadge";

const ORDER: Record<Severity, number> = { high: 0, medium: 1, low: 2 };

export function ReviewPanel({ document }: { document: DocumentOut }) {
  const { data: run, isLoading } = useLatestReview(document.id);
  const start = useStartReview(document.id);
  const { data: rules = [] } = useRules();
  const applicable = rules.filter((r) => r.enabled && r.genre === document.genre).length;
  const running = run?.status === "running" || start.isPending;
  const begin = () => start.mutate(undefined, { onError: () => toast.error("Không bắt đầu được lần rà soát.") });
  const save = (format: "md" | "json") =>
    run && download(`/reviews/${run.id}/export?format=${format}`).catch(() => toast.error("Không xuất được kết quả."));

  if (isLoading) return <Skeleton className="h-32 w-full" />;
  if (applicable === 0) {
    return (
      <p className="text-muted-foreground">
        Chưa có quy tắc nào đang bật cho thể loại {GENRE[document.genre].toLowerCase()}.{" "}
        <Link to="/rules" className="text-ink underline underline-offset-4">
          Thêm quy tắc rà soát
        </Link>
      </p>
    );
  }

  const findings = [...(run?.findings ?? [])].sort((a, b) => ORDER[a.severity] - ORDER[b.severity]);
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <p className="flex flex-1 items-center gap-2.5 text-muted-foreground" aria-live="polite">
          {running ? (
            <>
              <span className="size-1.5 animate-pulse rounded-full bg-ink" aria-hidden />
              Đang đối chiếu với {applicable} quy tắc…
            </>
          ) : run ? (
            `${findings.length} phát hiện, rà soát lúc ${formatTime(run.started_at)} theo ${applicable} quy tắc.`
          ) : (
            `Chưa rà soát tài liệu này. Có ${applicable} quy tắc đang bật cho thể loại ${GENRE[document.genre].toLowerCase()}.`
          )}
        </p>
        {run?.status === "done" && (
          <DropdownMenu>
            <DropdownMenuTrigger render={<Button variant="outline" size="sm" />}>
              <DownloadIcon /> Xuất
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-52">
              <DropdownMenuItem onClick={() => save("md")}>Xuất Markdown (.md)</DropdownMenuItem>
              <DropdownMenuItem onClick={() => save("json")}>Xuất JSON (.json)</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
        <Button size="sm" variant={run ? "outline" : "default"} disabled={running} onClick={begin}>
          {run ? <RotateCcwIcon /> : <ListChecksIcon />}
          {run ? "Rà soát lại" : "Chạy rà soát"}
        </Button>
      </div>
      {run?.status === "done" && findings.length === 0 && (
        <p className="rounded-lg bg-muted px-4 py-3">Không có phát hiện nào. Tài liệu đáp ứng mọi quy tắc đang bật.</p>
      )}
      {run?.status === "failed" && <p className="text-destructive">Lần rà soát này không hoàn tất. Hãy chạy lại.</p>}
      {!running && findings.length > 0 && (
        <ul className="flex flex-col gap-3">
          {findings.map((f) => (
            <Finding key={f.rule_id} finding={f} />
          ))}
        </ul>
      )}
    </div>
  );
}

function Finding({ finding: f }: { finding: FindingOut }) {
  const openSource = useUi((s) => s.openSource);
  const refs = f.passages.map((chunkId, i) => ({ label: `S${i + 1}`, chunkId }));
  return (
    <li className="flex flex-col gap-2 rounded-lg border bg-card p-4">
      <div className="flex items-center gap-2.5">
        <SeverityBadge severity={f.severity} />
        <h3 className="font-medium">{f.rule_name}</h3>
      </div>
      <p>{f.description}</p>
      {f.value && (
        <p className="text-sm">
          <span className="text-muted-foreground">Giá trị trong tài liệu: </span>
          {f.value}
        </p>
      )}
      <p className="text-sm text-muted-foreground">Căn cứ: {f.basis}</p>
      {refs.length > 0 ? (
        <div className="flex flex-wrap gap-2 pt-1">
          {refs.map((r) => (
            <Button key={r.chunkId} variant="outline" size="sm" onClick={() => openSource(refs, r.label)}>
              <FileSearchIcon /> {refs.length > 1 ? `Xem đoạn ${r.label.slice(1)}` : "Xem đoạn liên quan"}
            </Button>
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">Không có đoạn nào trong tài liệu tương ứng với quy tắc này.</p>
      )}
    </li>
  );
}
