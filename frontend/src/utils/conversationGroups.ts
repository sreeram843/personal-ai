import type { ConversationListItemData } from '../components/ConversationListItem';

export type ConversationDateGroup = 'today' | 'thisWeek' | 'older';

const GROUP_LABELS: Record<ConversationDateGroup, string> = {
  today: 'Today',
  thisWeek: 'This week',
  older: 'Older',
};

export function getConversationDateGroup(updatedAt?: number): ConversationDateGroup {
  if (!updatedAt) {
    return 'today';
  }
  const now = new Date();
  const date = new Date(updatedAt);
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfWeek = new Date(startOfToday);
  startOfWeek.setDate(startOfWeek.getDate() - 7);

  if (date >= startOfToday) {
    return 'today';
  }
  if (date >= startOfWeek) {
    return 'thisWeek';
  }
  return 'older';
}

export function groupConversationsByDate(
  items: ConversationListItemData[],
): Array<{ id: ConversationDateGroup; label: string; items: ConversationListItemData[] }> {
  const buckets: Record<ConversationDateGroup, ConversationListItemData[]> = {
    today: [],
    thisWeek: [],
    older: [],
  };

  for (const item of items) {
    buckets[getConversationDateGroup(item.updatedAt)].push(item);
  }

  return (['today', 'thisWeek', 'older'] as const)
    .filter((id) => buckets[id].length > 0)
    .map((id) => ({ id, label: GROUP_LABELS[id], items: buckets[id] }));
}
