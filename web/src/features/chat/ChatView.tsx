import { useChat } from "@ai-sdk/react";
import { Link, useParams } from "@tanstack/react-router";
import { CircleAlertIcon, RotateCcwIcon } from "lucide-react";
import { useEffect, useRef } from "react";
import { useConversation } from "@/api/client";
import { Button } from "@/components/ui/button";
import { turnsToMessages } from "@/lib/history";
import { AssistantMessage } from "./AssistantMessage";
import { ChatFrame } from "./ChatFrame";
import { chatFor } from "./chats";
import { Composer } from "./Composer";

export function ChatView() {
  const { conversationId } = useParams({ from: "/c/$conversationId" });
  const chat = chatFor(conversationId);
  const { messages, sendMessage, status, stop, error, regenerate, setMessages } = useChat({ chat });
  const { data: detail, isError: missing, isFetching } = useConversation(conversationId);
  const running = status === "submitted" || status === "streaming";

  // A reopened conversation starts from its stored turns, once they are fresh: a cached copy
  // may still hold answers deleted with their document (BR10).
  useEffect(() => {
    if (!isFetching && detail?.turns.length && chat.messages.length === 0) setMessages(turnsToMessages(detail.turns));
  }, [detail, isFetching, chat, setMessages]);

  const last = messages.at(-1);
  const lastFailed =
    status === "error" ||
    (!running && last?.role === "assistant" && last.parts.some((p) => p.type === "data-turn" && p.data.status === "failed"));

  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" });
  }, [messages, lastFailed]);

  return (
    <ChatFrame
      composer={<Composer onSend={(text) => sendMessage({ text })} onStop={stop} running={running} autoFocus />}
    >
      <div className="flex flex-col gap-8 pt-8 pb-4">
        {missing && messages.length === 0 && (
          <p className="text-muted-foreground">
            Không tìm thấy hội thoại này. Có thể nó đã bị xóa.{" "}
            <Link to="/" className="text-ink underline underline-offset-4">
              Bắt đầu hội thoại mới
            </Link>
          </p>
        )}
        {messages.map((m, i) =>
          m.role === "user" ? (
            <div key={m.id} className="ml-auto max-w-[85%] rounded-2xl rounded-br-md bg-secondary px-4 py-2.5">
              {m.parts.map((p) => (p.type === "text" ? p.text : "")).join("")}
            </div>
          ) : (
            <AssistantMessage
              key={m.id}
              message={m}
              running={running && i === messages.length - 1}
              failed={lastFailed && i === messages.length - 1}
            />
          ),
        )}
        {lastFailed && (
          <div role="alert" className="flex items-start gap-3 rounded-lg border bg-card px-4 py-3 text-sm">
            <CircleAlertIcon className="mt-0.5 size-4 shrink-0 text-destructive" />
            <div className="flex flex-1 flex-col gap-0.5">
              <p className="font-medium">Chưa có câu trả lời</p>
              <p className="text-muted-foreground">{error?.message || "Lần trước câu hỏi này không xử lý xong."}</p>
            </div>
            <Button variant="outline" size="sm" onClick={() => regenerate()}>
              <RotateCcwIcon /> Thử lại
            </Button>
          </div>
        )}
        <div ref={end} />
      </div>
    </ChatFrame>
  );
}
