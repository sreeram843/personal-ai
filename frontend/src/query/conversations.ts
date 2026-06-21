import type { ServerConversationSummary } from '../api';

export interface ConversationSummary {
  id: string;
  title: string;
  updatedAt?: number;
  messageCount: number;
  pinned: boolean;
}

export function mapConversationSummary(conversation: ServerConversationSummary): ConversationSummary {
  return {
    id: conversation.id,
    title: conversation.title?.trim() || 'New conversation',
    updatedAt: new Date(conversation.updated_at).getTime(),
    messageCount: conversation.message_count,
    pinned: Boolean(conversation.pinned),
  };
}
