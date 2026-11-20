import { DefaultChatTransport } from "ai";
import { API } from "@/api/client";
import type { VTMessage } from "@/api/stream";
import { useUi } from "@/stores/ui";

/** Sends only the new question and its scope; the server keeps the conversation history. */
export function chatTransport(conversationId: string) {
  return new DefaultChatTransport<VTMessage>({
    api: `${API}/conversations/${conversationId}/turns`,
    headers: { "x-vtagent": "1" },
    prepareSendMessagesRequest: ({ messages }) => {
      const last = messages[messages.length - 1];
      const question = last.parts.map((p) => (p.type === "text" ? p.text : "")).join("");
      return { body: { question, document_ids: useUi.getState().scope } };
    },
  });
}
