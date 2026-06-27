import { Copy, Pencil, RefreshCw, RotateCcw, Shield, ThumbsDown, ThumbsUp, User } from 'lucide-react';
import { useState } from 'react';
import type { ChatMessage } from '../types';
import { useThinkingPhrase } from '../hooks/useThinkingPhrase';
import {
  errorDescription,
  errorHeadline,
  resolveMessageError,
} from '../utils/chatErrors';
import { CuraiLogo } from './CuraiLogo';
import { ReasoningPanel } from './ReasoningPanel';
import { resolveAssistantLogoState } from './curaiLogoState';
import { AssistantMessageParts } from './liveData/LiveDataCards';
import { UserMessageEditor } from './UserMessageEditor';

interface Props {
  message: ChatMessage;
  isStreaming?: boolean;
  isEditing?: boolean;
  canEdit?: boolean;
  onCopy?: (message: ChatMessage) => void;
  onEdit?: (message: ChatMessage) => void;
  onEditResend?: (message: ChatMessage, newContent: string) => void;
  onEditCancel?: () => void;
  onRegenerate?: (message: ChatMessage) => void;
  onRetry?: (message: ChatMessage) => void;
  onEditFromError?: (message: ChatMessage) => void;
  onFeedback?: (message: ChatMessage, value: 'up' | 'down') => void;
  onApproveTools?: (toolIds: string[]) => void;
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

function formatTokenCount(count: number): string {
  if (count >= 1_000_000) {
    return `${(count / 1_000_000).toFixed(1).replace(/\.0$/, '')}M`;
  }
  if (count >= 1000) {
    return `${(count / 1000).toFixed(1).replace(/\.0$/, '')}k`;
  }
  return String(count);
}

function MessageErrorBanner({
  message,
  onRetry,
  onEditFromError,
}: {
  message: ChatMessage;
  onRetry?: (message: ChatMessage) => void;
  onEditFromError?: (message: ChatMessage) => void;
}) {
  const resolved = resolveMessageError(message);
  if (!resolved) {
    return null;
  }

  const { kind, detail } = resolved;
  const showRetry = kind !== 'refused';
  const showEdit = kind === 'refused';

  return (
    <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-3.5 py-3 text-sm">
      <div className="font-medium text-red-100">{errorHeadline(kind)}</div>
      <p className="mt-1 text-red-100/85">{errorDescription(kind, detail)}</p>
      {(showRetry || showEdit) && (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          {showRetry && (
            <button
              type="button"
              onClick={() => onRetry?.(message)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-1.5 text-xs font-medium text-red-100 transition hover:bg-red-500/20"
            >
              <RotateCcw className="h-3.5 w-3.5" aria-hidden />
              Retry
            </button>
          )}
          {showEdit && (
            <button
              type="button"
              onClick={() => onEditFromError?.(message)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-1.5 text-xs font-medium text-red-100 transition hover:bg-red-500/20"
            >
              <Pencil className="h-3.5 w-3.5" aria-hidden />
              Edit message
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export function ChatMessageBubble({
  message,
  isStreaming,
  isEditing = false,
  canEdit = true,
  onCopy,
  onEdit,
  onEditResend,
  onEditCancel,
  onRegenerate,
  onRetry,
  onEditFromError,
  onFeedback,
  onApproveTools,
}: Props) {
  const isUser = message.role === 'user';
  const [localEditing, setLocalEditing] = useState(false);
  const editing = isUser && (isEditing || localEditing);
  const thinkingPhrase = useThinkingPhrase(message, Boolean(isStreaming));

  const assistantLogoState = resolveAssistantLogoState(message, Boolean(isStreaming));
  const isThinking =
    !isUser && Boolean(isStreaming) && isPlaceholderAssistantContent(message.content);
  const messageError = !isUser ? resolveMessageError(message) : null;
  const showAssistantActions =
    !isUser &&
    !isStreaming &&
    !isPlaceholderAssistantContent(message.content) &&
    !messageError;
  const showUserActions = isUser && !isStreaming && !editing && canEdit;
  const showStreamingCaret =
    !isUser && Boolean(isStreaming) && !isPlaceholderAssistantContent(message.content);

  const startEdit = () => {
    setLocalEditing(true);
    onEdit?.(message);
  };

  const cancelEdit = () => {
    setLocalEditing(false);
    onEditCancel?.();
  };

  const submitEdit = (newContent: string) => {
    setLocalEditing(false);
    onEditResend?.(message, newContent);
  };

  return (
    <div className={`group/message flex w-full ${isUser ? 'justify-end' : 'justify-start'}`}>
      <article
        className={`flex w-full max-w-full ${isUser ? 'max-w-[92%] flex-row-reverse sm:max-w-[85%]' : 'flex-row'} gap-2.5`}
      >
        {isUser ? (
          <div className="mt-0.5 grid h-7 w-7 shrink-0 place-content-center rounded-full bg-[var(--ui-bg-elevated)] text-[var(--phosphor-dim)] ring-1 ring-[var(--ui-border)]">
            <User className="h-3.5 w-3.5" aria-hidden />
            <span className="sr-only">You</span>
          </div>
        ) : (
          <div className="mt-0.5 grid h-11 w-11 shrink-0 place-content-center">
            <CuraiLogo state={assistantLogoState} size={44} title="Assistant" />
          </div>
        )}

        <div className={`min-w-0 flex-1 ${isUser ? 'items-end' : 'items-start'} flex flex-col`}>
          <div
            className={
              isUser
                ? 'w-full rounded-2xl rounded-br-md bg-[var(--ui-bg-elevated)] px-3.5 py-2.5 text-[var(--phosphor)] ring-1 ring-[var(--ui-border)]'
                : 'py-0.5 text-[var(--phosphor)]'
            }
          >
            {editing ? (
              <UserMessageEditor
                initialContent={message.content}
                disabled={Boolean(isStreaming)}
                onSubmit={submitEdit}
                onCancel={cancelEdit}
              />
            ) : isThinking ? (
              <p
                className="thinking-status-text text-xs leading-relaxed text-[var(--phosphor-dim)]"
                aria-live="polite"
              >
                {thinkingPhrase}
              </p>
            ) : messageError ? (
              <MessageErrorBanner message={message} onRetry={onRetry} onEditFromError={onEditFromError} />
            ) : (
              <div className="space-y-2.5">
                <AssistantMessageParts
                  content={message.content}
                  blocks={message.blocks}
                  showStreamingCaret={showStreamingCaret}
                  showLiveSkeleton={message.showLiveSkeleton}
                />
                {message.pendingToolApprovals && message.pendingToolApprovals.length > 0 ? (
                  <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2.5 text-xs">
                    <div className="mb-2 flex items-center gap-1.5 font-medium text-amber-100">
                      <Shield className="h-3.5 w-3.5" aria-hidden />
                      Tools waiting for approval
                    </div>
                    <ul className="space-y-1.5 text-amber-50/90">
                      {message.pendingToolApprovals.map((item) => (
                        <li key={item.tool_id}>
                          <span className="font-medium">{item.name}</span>
                          <span className="text-amber-100/70"> · {item.risk_class}</span>
                        </li>
                      ))}
                    </ul>
                    {onApproveTools ? (
                      <button
                        type="button"
                        onClick={() => onApproveTools(message.pendingToolApprovals!.map((item) => item.tool_id))}
                        className="mt-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-xs font-medium text-amber-50 hover:bg-amber-500/20"
                      >
                        Approve and retry
                      </button>
                    ) : null}
                  </div>
                ) : null}
              </div>
            )}
          </div>

          {isUser && message.inputTokens !== undefined && !editing && (
            <span className="mt-1 text-xs tabular-nums text-[var(--phosphor-dim)]">
              {formatTokenCount(message.inputTokens)} tokens
            </span>
          )}

          {!isUser && <ReasoningPanel message={message} isStreaming={Boolean(isStreaming)} />}

          {showUserActions && (
            <div className="mt-1.5 flex flex-wrap items-center gap-0.5 opacity-100 transition-opacity md:opacity-0 md:group-hover/message:opacity-100 md:group-focus-within/message:opacity-100">
              <button
                type="button"
                onClick={() => onCopy?.(message)}
                className="touch-target grid h-10 w-10 shrink-0 place-content-center rounded-md text-[var(--phosphor-dim)] transition hover:bg-[var(--ui-bg-elevated)] hover:text-[var(--phosphor)] active:scale-[0.98] md:h-7 md:w-7"
                aria-label="Copy message"
                title="Copy markdown"
              >
                <Copy className="h-3.5 w-3.5" aria-hidden />
              </button>
              <button
                type="button"
                onClick={startEdit}
                className="touch-target grid h-10 w-10 shrink-0 place-content-center rounded-md text-[var(--phosphor-dim)] transition hover:bg-[var(--ui-bg-elevated)] hover:text-[var(--phosphor)] active:scale-[0.98] md:h-7 md:w-7"
                aria-label="Edit message"
                title="Edit and resend"
              >
                <Pencil className="h-3.5 w-3.5" aria-hidden />
              </button>
            </div>
          )}

          {showAssistantActions && (
            <div className="mt-1.5 flex flex-wrap items-center gap-0.5 opacity-100 transition-opacity md:opacity-0 md:group-hover/message:opacity-100 md:group-focus-within/message:opacity-100">
              <button
                type="button"
                onClick={() => onCopy?.(message)}
                className="touch-target grid h-10 w-10 shrink-0 place-content-center rounded-md text-[var(--phosphor-dim)] transition hover:bg-[var(--ui-bg-elevated)] hover:text-[var(--phosphor)] active:scale-[0.98] md:h-7 md:w-7"
                aria-label="Copy message"
                title="Copy markdown"
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
              {message.outputTokens !== undefined && (
                <span className="ml-1 self-center text-xs tabular-nums text-[var(--phosphor-dim)]">
                  {formatTokenCount(message.outputTokens)} tokens
                </span>
              )}
            </div>
          )}
        </div>
      </article>
    </div>
  );
}
