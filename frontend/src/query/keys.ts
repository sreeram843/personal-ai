export const queryKeys = {
  authConfig: ['auth', 'config'] as const,
  auth: ['auth'] as const,
  currentUser: ['auth', 'me'] as const,
  conversations: ['conversations'] as const,
  messages: (conversationId: string | null) => ['conversations', conversationId, 'messages'] as const,
};
