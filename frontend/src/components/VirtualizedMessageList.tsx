import { useEffect, useRef, type RefObject } from 'react';
import type { ChatMessage } from '../types';
import { ChatMessageBubble } from './ChatMessageBubble';

interface Props {
  scrollRef: RefObject<HTMLDivElement | null>;
  messages: ChatMessage[];
  isLoading: boolean;
  onCopy: (message: ChatMessage) => void;
  onRegenerate: (message: ChatMessage) => void;
  onFeedback: () => void;
}

/** Simple stacked message list — avoids virtualizer height overlap on long markdown replies. */
export function VirtualizedMessageList({
  scrollRef,
  messages,
  isLoading,
  onCopy,
  onRegenerate,
  onFeedback,
}: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const lastMessage = messages[messages.length - 1];

  useEffect(() => {
    const container = scrollRef.current;
    if (!container || messages.length === 0) return;

    requestAnimationFrame(() => {
      bottomRef.current?.scrollIntoView({ block: 'end' });
    });
  }, [messages.length, lastMessage?.id, lastMessage?.content, scrollRef]);

  return (
    <div className="flex w-full flex-col gap-2">
      {messages.map((message, index) => (
        <ChatMessageBubble
          key={message.id}
          message={message}
          isStreaming={isLoading && index === messages.length - 1}
          onCopy={onCopy}
          onRegenerate={onRegenerate}
          onFeedback={onFeedback}
        />
      ))}
      <div ref={bottomRef} aria-hidden className="h-px w-full shrink-0" />
    </div>
  );
}
