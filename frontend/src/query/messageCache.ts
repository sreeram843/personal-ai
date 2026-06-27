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
  const next = [...previous, userMessage, assistantMessage];
  writeCachedMessages(queryClient, conversationId, next);
  return next;
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

/**
 * Prefer cached turns while the server is still persisting (fewer rows) or the client
 * is waiting on a long-running assistant reply.
 */
export function mergeFetchedMessages(fetched: ChatMessage[], cached: ChatMessage[]): ChatMessage[] {
  if (cached.length === 0) {
    return fetched;
  }
  if (fetched.length === 0) {
    return cached;
  }
  if (fetched.length < cached.length) {
    return cached;
  }

  const pendingAssistant = cached[cached.length - 1];
  if (
    pendingAssistant?.role === 'assistant' &&
    pendingAssistant.content.trim() === '' &&
    fetched.length === cached.length
  ) {
    return cached;
  }

  return mergeAssistantLatency(fetched, cached);
}

/** Preserve client-measured latency when a refetch replaces optimistic message ids. */
export function mergeAssistantLatency(fetched: ChatMessage[], previous: ChatMessage[]): ChatMessage[] {
  const latencyByContent = new Map<string, number>();
  for (const message of previous) {
    if (message.role === 'assistant' && message.latencyMs !== undefined) {
      const key = message.content.trim();
      if (key) {
        latencyByContent.set(key, message.latencyMs);
      }
    }
  }

  if (latencyByContent.size === 0) {
    return fetched;
  }

  return fetched.map((message) => {
    if (message.role !== 'assistant' || message.latencyMs !== undefined) {
      return message;
    }
    const fromPrevious = latencyByContent.get(message.content.trim());
    return fromPrevious !== undefined ? { ...message, latencyMs: fromPrevious } : message;
  });
}
