import { useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useCreateConversation, useDocuments } from "@/api/client";
import { chatFor } from "./chats";
import { ChatFrame } from "./ChatFrame";
import { Composer } from "./Composer";

const MOCK = import.meta.env.VITE_MOCK === "1";

export function NewChat() {
  const navigate = useNavigate();
  const create = useCreateConversation();
  const { data: documents = [] } = useDocuments();
  // Questions that trigger each scripted answer of the browser mock; absent from real builds.
  const [samples, setSamples] = useState<string[]>([]);
  useEffect(() => {
    if (MOCK) import("@/mocks/scenarios").then((m) => setSamples(m.SAMPLE_QUESTIONS));
  }, []);
  const ask = (question: string) =>
    create.mutate(question.length > 60 ? `${question.slice(0, 60).trimEnd()}…` : question, {
      onSuccess: (c) => {
        chatFor(c.id).sendMessage({ text: question });
        navigate({ to: "/c/$conversationId", params: { conversationId: c.id } });
      },
    });

  return (
    <ChatFrame composer={<Composer onSend={ask} running={create.isPending} autoFocus />}>
      <div className="flex min-h-[55vh] flex-col justify-end gap-3 pb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-ink">Hỏi về tài liệu của bạn</h1>
        <p className="max-w-[38rem] text-muted-foreground">
          Câu trả lời chỉ dựa trên {documents.length} tài liệu đã nạp. Mỗi ý kèm trích dẫn tới điều, khoản và trang, và
          được đối chiếu lại với nguồn trước khi hiện ra.
        </p>
        {samples.length > 0 && (
          <div className="mt-3 flex flex-col items-start gap-1 text-sm">
            <span className="text-muted-foreground">Thử với dữ liệu mẫu:</span>
            {samples.map((q) => (
              <button key={q} className="text-left text-ink underline-offset-4 hover:underline" onClick={() => ask(q)}>
                {q}
              </button>
            ))}
          </div>
        )}
      </div>
    </ChatFrame>
  );
}
