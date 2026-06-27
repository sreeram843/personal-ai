import type { ContentBlock, MessagePart } from '../types/liveData';

/** Build ordered message parts: cards first, then trailing markdown text. */
export function buildMessageParts(content: string, blocks?: ContentBlock[]): MessagePart[] {
  const parts: MessagePart[] = [];
  for (const block of blocks ?? []) {
    if (block.type === 'text') {
      continue;
    }
    parts.push({
      kind: 'card',
      type: block.type,
      data: block.data,
      subscriptionKey: block.subscription_key,
    });
  }
  const text = content.trim();
  if (text) {
    parts.push({ kind: 'text', text: content });
  }
  return parts;
}
