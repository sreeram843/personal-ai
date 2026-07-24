import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createConversation,
  deleteConversation,
  ensureAuthToken,
  fetchAuthConfig,
  fetchConversationMessages,
  fetchCurrentUser,
  listConversations,
  mapServerMessage,
  updateConversation,
} from '../api';
import { clearAuthToken, getAuthToken } from '../auth';
import { mapConversationSummary } from './conversations';
import { queryKeys } from './keys';
import type { ConversationMode } from '../types';
import { mergeFetchedMessages, messageQueryKey, readCachedMessages } from './messageCache';

export function useAuthConfig() {
  return useQuery({
    queryKey: queryKeys.authConfig,
    queryFn: fetchAuthConfig,
    staleTime: Number.POSITIVE_INFINITY,
    retry: 2,
  });
}

export function useAuthBootstrap(enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.auth,
    queryFn: ensureAuthToken,
    enabled,
    staleTime: Number.POSITIVE_INFINITY,
    retry: 2,
  });
}

export function useCurrentUser(enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.currentUser,
    queryFn: fetchCurrentUser,
    enabled: enabled && Boolean(getAuthToken()),
    staleTime: 60_000,
    retry: false,
  });
}

export function useLogout() {
  const queryClient = useQueryClient();

  return () => {
    clearAuthToken();
    queryClient.clear();
  };
}

export function useConversations(enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.conversations,
    queryFn: async () => {
      const rows = await listConversations();
      return rows.map(mapConversationSummary);
    },
    enabled,
  });
}

export function useConversationMessages(conversationId: string | null, enabled: boolean) {
  const queryClient = useQueryClient();

  return useQuery({
    queryKey: messageQueryKey(conversationId),
    queryFn: async () => {
      const cached = readCachedMessages(queryClient, conversationId);
      if (!conversationId) {
        return cached;
      }
      const stored = await fetchConversationMessages(conversationId);
      const mapped = stored.map(mapServerMessage);
      return mergeFetchedMessages(mapped, cached);
    },
    enabled,
    placeholderData: (previous) => previous,
    refetchOnWindowFocus: false,
    staleTime: 30_000,
  });
}

export function useCreateConversation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ mode, assistantId }: { mode: ConversationMode; assistantId?: string | null }) =>
      createConversation(mode, undefined, assistantId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.conversations });
    },
  });
}

export function useDeleteConversation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (conversationId: string) => deleteConversation(conversationId),
    onSuccess: (_result, conversationId) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.conversations });
      void queryClient.removeQueries({ queryKey: messageQueryKey(conversationId) });
    },
  });
}

export function useUpdateConversation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      conversationId,
      title,
      pinned,
    }: {
      conversationId: string;
      title?: string;
      pinned?: boolean;
    }) => updateConversation(conversationId, { title, pinned }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.conversations });
    },
  });
}

export function useInvalidateConversationData() {
  const queryClient = useQueryClient();

  return {
    invalidateAll: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.conversations });
    },
    invalidateMessages: (conversationId: string | null) => {
      void queryClient.invalidateQueries({ queryKey: messageQueryKey(conversationId) });
    },
    invalidateAfterSend: (conversationId: string | null) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.conversations });
      // Keep the optimistic message cache; refetching mid-turn caused blank flashes.
      void conversationId;
    },
  };
}
