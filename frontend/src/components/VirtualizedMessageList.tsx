import { useEffect, useState, type RefObject } from 'react';
import { Virtuoso } from 'react-virtuoso';
import type { ChatMessage } from '../types';
import { ChatMessageBubble } from './ChatMessageBubble';

const VIRTUALIZE_THRESHOLD = 40;

interface Props {
  scrollRef: RefObject<HTMLDivElement | null>;
  messages: ChatMessage[];
  isLoading: boolean;
  isNearBottom: boolean;
  editingUserMessageId: string | null;
  hideActions?: boolean;
  onCopy: (message: ChatMessage) => void;
  onEditResend: (message: ChatMessage, newContent: string) => void;
  onEditCancel: () => void;
  onEditFromError: (message: ChatMessage) => void;
  onRegenerate: (message: ChatMessage) => void;
  onRetry: (message: ChatMessage) => void;
  onFeedback: () => void;
  onApproveTools?: (toolIds: string[]) => void;
}

function renderBubble(
  message: ChatMessage,
  index: number,
  messages: ChatMessage[],
  isLoading: boolean,
  editingUserMessageId: string | null,
  handlers: Omit<Props, 'scrollRef' | 'messages' | 'isLoading' | 'isNearBottom' | 'editingUserMessageId'>,
) {
  return (
    <ChatMessageBubble
      message={message}
      isStreaming={isLoading && index === messages.length - 1}
      isEditing={message.id === editingUserMessageId}
      canEdit={!isLoading && !handlers.hideActions}
      hideActions={handlers.hideActions}
      onCopy={handlers.onCopy}
      onEditResend={handlers.onEditResend}
      onEditCancel={handlers.onEditCancel}
      onEditFromError={handlers.onEditFromError}
      onRegenerate={handlers.onRegenerate}
      onRetry={handlers.onRetry}
      onFeedback={handlers.onFeedback}
      onApproveTools={handlers.onApproveTools}
    />
  );
}

export function VirtualizedMessageList({
  scrollRef,
  messages,
  isLoading,
  isNearBottom,
  editingUserMessageId,
  hideActions = false,
  onCopy,
  onEditResend,
  onEditCancel,
  onEditFromError,
  onRegenerate,
  onRetry,
  onFeedback,
  onApproveTools,
}: Props) {
  const [scrollParent, setScrollParent] = useState<HTMLElement | null>(null);
  const handlers = {
    hideActions,
    onCopy,
    onEditResend,
    onEditCancel,
    onEditFromError,
    onRegenerate,
    onRetry,
    onFeedback,
    onApproveTools,
  };

  useEffect(() => {
    setScrollParent(scrollRef.current);
  }, [scrollRef]);

  if (messages.length === 0) {
    return null;
  }

  if (messages.length <= VIRTUALIZE_THRESHOLD || !scrollParent) {
    return (
      <div className="flex w-full flex-col gap-2">
        {messages.map((message, index) => (
          <div key={message.id} className="message-enter">
            {renderBubble(message, index, messages, isLoading, editingUserMessageId, handlers)}
          </div>
        ))}
        <div aria-hidden className="h-px w-full shrink-0" />
      </div>
    );
  }

  return (
    <Virtuoso
      customScrollParent={scrollParent}
      data={messages}
      followOutput={isNearBottom ? 'auto' : false}
      increaseViewportBy={{ top: 500, bottom: 500 }}
      computeItemKey={(_, message) => message.id}
      itemContent={(index, message) => (
        <div className="message-enter pb-2">
          {renderBubble(message, index, messages, isLoading, editingUserMessageId, handlers)}
        </div>
      )}
      components={{
        Footer: () => <div aria-hidden className="h-px w-full shrink-0" />,
      }}
    />
  );
}
