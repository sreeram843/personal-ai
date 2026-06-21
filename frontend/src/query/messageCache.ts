import type { QueryClient } from '@tanstack/react-query';
import type { ChatMessage } from '../types';
import { queryKeys } from './keys';

export function messageQueryKey(conversationId: string | null) {
  return queryKeys.messages(conversationId);
}

export function readCachedMessages(queryClient: QueryClient, conversationId: string | null): ChatMessage[] {
  return queryClient.getQueryData<ChatMessage[]>(messageQueryKey(conversationId)) ?? [];
}

export function writeCachedMessages(
  queryClient: QueryClient,
  conversationId: string | null,
  messages: ChatMessage[],
) {
  queryClient.setQueryData(messageQueryKey(conversationId), messages);
}

export function appendOptimisticSend(
  queryClient: QueryClient,
  conversationId: string | null,
  userMessage: ChatMessage,
  assistantMessage: ChatMessage,
): ChatMessage[] {
  const previous = readCachedMessages(queryClient, conversationId);
  writeCachedMessages(queryClient, conversationId, [...previous, userMessage, assistantMessage]);
  return previous;
}

export function updateCachedMessage(
  queryClient: QueryClient,
  conversationId: string | null,
  messageId: string,
  updater: (message: ChatMessage) => ChatMessage,
) {
  writeCachedMessages(
    queryClient,
    conversationId,
    readCachedMessages(queryClient, conversationId).map((message) =>
      message.id === messageId ? updater(message) : message,
    ),
  );
}

export function promoteDraftMessages(queryClient: QueryClient, conversationId: string) {
  const draft = readCachedMessages(queryClient, null);
  if (draft.length > 0) {
    writeCachedMessages(queryClient, conversationId, draft);
  }
  queryClient.removeQueries({ queryKey: messageQueryKey(null) });
}
