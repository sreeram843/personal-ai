import { Copy, RefreshCw, ThumbsDown, ThumbsUp, User } from 'lucide-react';
import type { ChatMessage } from '../types';
import { CuraiLogo } from './CuraiLogo';
import { resolveAssistantLogoState } from './curaiLogoState';
import { MessageContent } from './MessageContent';

interface Props {
  message: ChatMessage;
  isStreaming?: boolean;
  onCopy?: (message: ChatMessage) => void;
  onRegenerate?: (message: ChatMessage) => void;
  onFeedback?: (message: ChatMessage, value: 'up' | 'down') => void;
}

function isPlaceholderAssistantContent(content: string): boolean {
  const trimmed = content.trim();
  return trimmed === '' || trimmed === 'Coordinating workflow...';
}

function formatLatency(ms: number): string {
  if (ms >= 1000) {
    return `${(ms / 1000).toFixed(1)}s`;
  }
  return `${Math.round(ms)} ms`;
}

export function ChatMessageBubble({ message, isStreaming, onCopy, onRegenerate, onFeedback }: Props) {
  const isUser = message.role === 'user';

  const assistantLogoState = resolveAssistantLogoState(message, Boolean(isStreaming));
  const streamingLogoOnly =
    !isUser && Boolean(isStreaming) && isPlaceholderAssistantContent(message.content);
  const showAssistantActions =
    !isUser &&
    !isStreaming &&
    !isPlaceholderAssistantContent(message.content) &&
    !message.content.startsWith('⚠️');

  if (streamingLogoOnly) {
    return (
      <div className="flex w-full justify-start py-3">
        <CuraiLogo state={assistantLogoState} size={52} title="Assistant" />
        <span className="sr-only">Assistant is responding</span>
      </div>
    );
  }

  return (
    <div className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'}`}>
      <article className={`flex w-full max-w-full ${isUser ? 'max-w-[92%] flex-row-reverse sm:max-w-[85%]' : 'flex-row'} gap-2.5`}>
        {isUser ? (
          <div className="mt-0.5 grid h-7 w-7 shrink-0 place-content-center rounded-full bg-[var(--ui-bg-elevated)] text-[var(--phosphor-dim)] ring-1 ring-[var(--ui-border)]">
            <User className="h-3.5 w-3.5" aria-hidden />
            <span className="sr-only">You</span>
          </div>
        ) : (
          <div className="mt-0.5 grid h-7 w-7 shrink-0 place-content-center">
            <CuraiLogo state={assistantLogoState} size={28} title="Assistant" />
          </div>
        )}

        <div className={`min-w-0 flex-1 ${isUser ? 'items-end' : 'items-start'} flex flex-col`}>
          <div
            className={
              isUser
                ? 'rounded-2xl rounded-br-md bg-[var(--ui-bg-elevated)] px-3.5 py-2.5 text-[var(--phosphor)] ring-1 ring-[var(--ui-border)]'
                : 'py-0.5 text-[var(--phosphor)]'
            }
          >
            <MessageContent content={message.content} />
          </div>

          {showAssistantActions && (
            <div className="mt-1.5 flex flex-wrap items-center gap-0.5">
              <button
                type="button"
                onClick={() => onCopy?.(message)}
                className="touch-target grid h-10 w-10 shrink-0 place-content-center rounded-md text-[var(--phosphor-dim)] transition hover:bg-[var(--ui-bg-elevated)] hover:text-[var(--phosphor)] active:scale-[0.98] md:h-7 md:w-7"
                aria-label="Copy message"
                title="Copy"
              >
                <Copy className="h-3.5 w-3.5" aria-hidden />
              </button>
              <button
                type="button"
                onClick={() => onRegenerate?.(message)}
                className="touch-target grid h-10 w-10 shrink-0 place-content-center rounded-md text-[var(--phosphor-dim)] transition hover:bg-[var(--ui-bg-elevated)] hover:text-[var(--phosphor)] active:scale-[0.98] md:h-7 md:w-7"
                aria-label="Regenerate"
                title="Regenerate"
              >
                <RefreshCw className="h-3.5 w-3.5" aria-hidden />
              </button>
              <button
                type="button"
                onClick={() => onFeedback?.(message, 'up')}
                className="touch-target grid h-10 w-10 shrink-0 place-content-center rounded-md text-[var(--phosphor-dim)] transition hover:bg-[var(--ui-bg-elevated)] hover:text-[var(--phosphor)] active:scale-[0.98] md:h-7 md:w-7"
                aria-label="Thumbs up"
                title="Helpful"
              >
                <ThumbsUp className="h-3.5 w-3.5" aria-hidden />
              </button>
              <button
                type="button"
                onClick={() => onFeedback?.(message, 'down')}
                className="touch-target grid h-10 w-10 shrink-0 place-content-center rounded-md text-[var(--phosphor-dim)] transition hover:bg-[var(--ui-bg-elevated)] hover:text-[var(--phosphor)] active:scale-[0.98] md:h-7 md:w-7"
                aria-label="Thumbs down"
                title="Not helpful"
              >
                <ThumbsDown className="h-3.5 w-3.5" aria-hidden />
              </button>
              {message.latencyMs !== undefined && (
                <span className="ml-1 self-center text-xs tabular-nums text-[var(--phosphor-dim)]">
                  {formatLatency(message.latencyMs)}
                </span>
              )}
            </div>
          )}
        </div>
      </article>
    </div>
  );
}
