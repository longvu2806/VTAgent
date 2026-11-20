import { ArrowUpIcon, FileTextIcon, SquareIcon, XIcon } from "lucide-react";
import { useState } from "react";
import { useDocuments } from "@/api/client";
import { Button } from "@/components/ui/button";
import { UploadChip } from "@/features/documents/UploadChip";
import { useUploads } from "@/features/documents/uploads";
import { useUi } from "@/stores/ui";
import { AttachMenu } from "./AttachMenu";

interface Props {
  onSend: (question: string) => void;
  onStop?: () => void;
  running?: boolean;
  autoFocus?: boolean;
}

export function Composer({ onSend, onStop, running = false, autoFocus }: Props) {
  const [text, setText] = useState("");
  const { scope, toggleScope } = useUi();
  const uploads = useUploads((s) => s.items);
  const { data: documents = [] } = useDocuments();
  const scoped = documents.filter((d) => scope.includes(d.id));

  const send = () => {
    const question = text.trim();
    if (!question || running) return;
    onSend(question);
    setText("");
  };

  return (
    <form
      className="flex flex-col gap-2 rounded-xl border bg-card p-2.5 shadow-[0_1px_2px_rgb(28_46_74/0.06)] focus-within:border-ring"
      onSubmit={(e) => {
        e.preventDefault();
        send();
      }}
    >
      {(uploads.length > 0 || scoped.length > 0) && (
        <div className="flex flex-wrap gap-1.5 px-1">
          {uploads.map((u) => (
            <UploadChip key={u.jobId} upload={u} />
          ))}
          {scoped.map((d) => (
            <span key={d.id} className="flex max-w-64 items-center gap-1.5 rounded-md bg-secondary py-1 pr-1 pl-2 text-xs">
              <FileTextIcon className="size-3.5 shrink-0 text-ink" />
              <span className="truncate">{d.title}</span>
              <button type="button" aria-label={`Bỏ ${d.title} khỏi phạm vi`} onClick={() => toggleScope(d.id)}>
                <XIcon className="size-3.5" />
              </button>
            </span>
          ))}
        </div>
      )}
      <textarea
        autoFocus={autoFocus}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            send();
          }
        }}
        rows={1}
        placeholder={scoped.length ? "Hỏi trong các tài liệu đã chọn" : "Hỏi về tài liệu đã nạp"}
        aria-label="Câu hỏi"
        className="field-sizing-content max-h-48 min-h-10 resize-none bg-transparent px-1.5 py-1 text-[1rem] outline-none placeholder:text-muted-foreground"
      />
      <div className="flex items-center gap-2">
        <AttachMenu />
        <span className="hidden text-xs text-muted-foreground sm:inline">Enter để gửi, Shift + Enter để xuống dòng</span>
        {running ? (
          <Button type="button" size="icon" className="ml-auto rounded-full" aria-label="Dừng" onClick={onStop}>
            <SquareIcon className="fill-current" />
          </Button>
        ) : (
          <Button type="submit" size="icon" className="ml-auto rounded-full" aria-label="Gửi câu hỏi" disabled={!text.trim()}>
            <ArrowUpIcon />
          </Button>
        )}
      </div>
    </form>
  );
}
