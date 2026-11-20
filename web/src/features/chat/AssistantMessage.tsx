// One answer: a live stage line, the Analyst's calculations and the collapsible draft while
// the pipeline runs, then the verified answer with its citations and a verification summary.
import type { DynamicToolUIPart } from "ai";
import { CheckIcon, ChevronRightIcon, CircleDashedIcon, CopyIcon, DownloadIcon, SearchXIcon, TriangleAlertIcon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Streamdown } from "streamdown";
import { download } from "@/api/client";
import type { TurnData, VTMessage } from "@/api/stream";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { splitSentences } from "@/lib/answer";
import { stageText } from "@/lib/labels";
import { FinalAnswer } from "./FinalAnswer";
import { ToolCard } from "./ToolCard";

function partsOf(message: VTMessage) {
  let stage, verification, citations, turn;
  const draft: string[] = [];
  const tools: DynamicToolUIPart[] = [];
  let answer = "";
  for (const p of message.parts) {
    if (p.type === "data-stage") stage = p.data;
    else if (p.type === "data-verification") verification = p.data;
    else if (p.type === "data-citations") citations = p.data;
    else if (p.type === "data-turn") turn = p.data;
    else if (p.type === "dynamic-tool") tools.push(p);
    else if (p.type === "reasoning") draft.push(p.text);
    else if (p.type === "text") answer += p.text;
  }
  return { stage, verification, citations: citations ?? [], turn, tools, draft: draft.join("\n\n"), answer };
}

interface Props {
  message: VTMessage;
  running: boolean;
  /** The turn failed and the thread shows the error with a retry below it. */
  failed: boolean;
}

export function AssistantMessage({ message, running, failed }: Props) {
  const { stage, verification, citations, turn, tools, draft, answer } = partsOf(message);
  const [draftOpen, setDraftOpen] = useState(false);
  const verified = answer.length > 0;

  return (
    <article className="flex flex-col gap-3">
      {!verified && !failed && stage && (
        <p className="flex items-center gap-2.5 text-sm text-muted-foreground" aria-live="polite">
          {running && <span className="size-1.5 animate-pulse rounded-full bg-ink" aria-hidden />}
          {running ? stageText(stage) : "Đã dừng trước khi có câu trả lời đã kiểm chứng."}
        </p>
      )}
      {!failed && turn?.status === "failed" && (
        <p className="text-sm text-muted-foreground">Câu hỏi này không có câu trả lời do lỗi khi xử lý.</p>
      )}
      {tools.map((t) => (
        <ToolCard key={t.toolCallId} part={t} citations={citations} />
      ))}
      {draft && (
        <Collapsible open={draftOpen} onOpenChange={setDraftOpen}>
          <CollapsibleTrigger className="group flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
            <ChevronRightIcon className="size-4 transition-transform group-data-[panel-open]:rotate-90" />
            {verified ? "Bản nháp" : running ? "Bản nháp đang soạn, chưa kiểm chứng" : "Bản nháp chưa kiểm chứng"}
          </CollapsibleTrigger>
          <CollapsibleContent>
            <Streamdown
              mode={verified || !running ? "static" : "streaming"}
              className="mt-2 border-l-2 border-border pl-3 text-sm leading-relaxed text-muted-foreground"
            >
              {draft}
            </Streamdown>
          </CollapsibleContent>
        </Collapsible>
      )}
      {verified && turn?.status === "not_found" && <NotFound text={answer} />}
      {verified && turn?.status !== "not_found" && (
        <div className="flex animate-in flex-col gap-3 duration-300 fade-in-0">
          <FinalAnswer text={answer} citations={citations} verification={verification} />
          {turn?.status === "partial" && turn.missing && (
            <p className="flex gap-2.5 rounded-lg bg-caution-soft px-3.5 py-2.5 text-sm">
              <CircleDashedIcon className="mt-0.5 size-4 shrink-0 text-caution" />
              <span>
                <span className="font-medium text-caution">Chưa tìm thấy: </span>
                {turn.missing}
              </span>
            </p>
          )}
          <AnswerFooter answer={answer} turn={turn} flagged={verification?.sentences.filter((s) => !s.supported).length ?? 0} />
        </div>
      )}
    </article>
  );
}

/** The fixed refusal (FR-17): nothing in the loaded documents answers the question. */
function NotFound({ text }: { text: string }) {
  return (
    <div className="flex animate-in items-start gap-3 rounded-lg bg-muted px-4 py-3 duration-300 fade-in-0">
      <SearchXIcon className="mt-0.5 size-4.5 shrink-0 text-muted-foreground" />
      <div className="flex flex-col gap-0.5">
        <p>{text}</p>
        <p className="text-sm text-muted-foreground">
          Thử hỏi theo cách khác, chọn thêm tài liệu, hoặc nạp tài liệu có nội dung này.
        </p>
      </div>
    </div>
  );
}

function AnswerFooter({ answer, turn, flagged }: { answer: string; turn: TurnData | undefined; flagged: number }) {
  const [copied, setCopied] = useState(false);
  const sentences = splitSentences(answer).length;
  const save = (format: "md" | "json") =>
    turn && download(`/turns/${turn.id}/export?format=${format}`).catch(() => toast.error("Không xuất được câu trả lời."));
  return (
    <div className="flex items-center gap-1 text-sm text-muted-foreground">
      {flagged === 0 ? (
        <span className="flex items-center gap-1.5">
          <CheckIcon className="size-4 text-ink" /> Đã đối chiếu {sentences} câu với nguồn
        </span>
      ) : (
        <span className="flex items-center gap-1.5 text-caution">
          <TriangleAlertIcon className="size-4" /> {flagged} câu chưa đủ căn cứ
        </span>
      )}
      <Button
        variant="ghost"
        size="icon-sm"
        className="ml-auto"
        aria-label="Sao chép câu trả lời"
        onClick={() => {
          navigator.clipboard.writeText(answer.replace(/\[S\d+(?:\s*,\s*S\d+)*\]/g, "").trim());
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        }}
      >
        {copied ? <CheckIcon /> : <CopyIcon />}
      </Button>
      {turn && (
        <DropdownMenu>
          <DropdownMenuTrigger render={<Button variant="ghost" size="icon-sm" aria-label="Xuất câu trả lời" />}>
            <DownloadIcon />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-52">
            <DropdownMenuItem onClick={() => save("md")}>Xuất Markdown (.md)</DropdownMenuItem>
            <DropdownMenuItem onClick={() => save("json")}>Xuất JSON (.json)</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </div>
  );
}
