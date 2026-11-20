// One AI SDK chat per conversation, kept outside the component tree so an answer keeps
// streaming when the user switches conversations, and React remounts do not stop it.
import { Chat } from "@ai-sdk/react";
import type { VTMessage } from "@/api/stream";
import { queryClient } from "@/lib/query";
import { chatTransport } from "./transport";

const chats = new Map<string, Chat<VTMessage>>();

/** Stop and drop the chat of a deleted conversation. */
export function forgetChat(conversationId: string) {
  chats.get(conversationId)?.stop();
  chats.delete(conversationId);
}

/** Drop idle chats, so they reload from the server after answers were deleted (BR10). */
export function forgetIdleChats() {
  for (const [id, chat] of chats) if (chat.status !== "submitted" && chat.status !== "streaming") chats.delete(id);
}

export function chatFor(conversationId: string): Chat<VTMessage> {
  let chat = chats.get(conversationId);
  if (!chat) {
    chat = new Chat<VTMessage>({
      id: conversationId,
      transport: chatTransport(conversationId),
      // The sidebar orders conversations by their latest answer.
      onFinish: () => queryClient.invalidateQueries({ queryKey: ["conversations"] }),
    });
    chats.set(conversationId, chat);
  }
  return chat;
}
