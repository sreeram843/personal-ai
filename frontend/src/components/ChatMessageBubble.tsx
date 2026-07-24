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
  /** Hide copy/edit/regenerate/feedback controls (portfolio demo). */
  hideActions?: boolean;
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
    <div className="flex flex-col gap-2 rounded-xl border border-[rgba(239,68,68,0.35)] bg-[rgba(239,68,68,0.1)] px-4 py-3 text-sm">
      <div className="font-semibold text-[#f87171]">{errorHeadline(kind)}</div>
      <p className="text-[var(--ui-text-secondary)]">{errorDescription(kind, detail)}</p>
      {(showRetry || showEdit) && (
        <div className="flex flex-wrap items-center gap-2">
          {showRetry && (
            <button
              type="button"
              onClick={() => onRetry?.(message)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-[rgba(239,68,68,0.35)] bg-[rgba(239,68,68,0.15)] px-[13px] py-[7px] text-xs font-semibold text-[#f87171] transition hover:bg-[rgba(239,68,68,0.25)]"
            >
              <RotateCcw className="h-3.5 w-3.5" aria-hidden />
              Retry
            </button>
          )}
          {showEdit && (
            <button
              type="button"
              onClick={() => onEditFromError?.(message)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-[rgba(239,68,68,0.35)] bg-[rgba(239,68,68,0.15)] px-[13px] py-[7px] text-xs font-semibold text-[#f87171] transition hover:bg-[rgba(239,68,68,0.25)]"
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
  hideActions = false,
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
  const editing = isUser && (isEditing || localEditing) && !hideActions;
  const thinkingPhrase = useThinkingPhrase(message, Boolean(isStreaming));

  const assistantLogoState = resolveAssistantLogoState(message, Boolean(isStreaming));
  const isThinking =
    !isUser && Boolean(isStreaming) && isPlaceholderAssistantContent(message.content);
  const messageError = !isUser ? resolveMessageError(message) : null;
  const showAssistantActions =
    !hideActions &&
    !isUser &&
    !isStreaming &&
    !isPlaceholderAssistantContent(message.content) &&
    !messageError;
  const showUserActions = !hideActions && isUser && !isStreaming && !editing && canEdit;
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
        className={`flex w-full max-w-full ${isUser ? 'max-w-[66%] flex-row-reverse' : 'max-w-[90%] flex-row'} gap-2.5`}
      >
        {isUser ? (
          <div className="mt-0.5 grid h-7 w-7 shrink-0 place-content-center rounded-full bg-[var(--ui-bg-elevated)] text-[var(--phosphor-dim)] ring-1 ring-[var(--ui-border)]">
            <User className="h-3.5 w-3.5" aria-hidden />
            <span className="sr-only">You</span>
          </div>
        ) : (
          <div className="mt-0.5 grid h-[30px] w-[30px] shrink-0 place-content-center rounded-[9px] bg-[var(--ui-bg-elevated)]">
            <CuraiLogo state={assistantLogoState} size={19} title="Assistant" />
          </div>
        )}

        <div className={`min-w-0 flex-1 ${isUser ? 'items-end' : 'items-start'} flex flex-col`}>
          {isThinking ? (
            <div
              className="thinking-status-chip inline-flex max-w-full items-center gap-2 self-start rounded-full border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] px-3.5 py-2"
              aria-live="polite"
            >
              <span className="thinking-status-dot h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--ui-accent)]" aria-hidden />
              <p className="thinking-status-text truncate text-xs leading-relaxed text-[var(--phosphor-dim)]">
                {thinkingPhrase}
              </p>
            </div>
          ) : (
            <div
              className={
                isUser
                  ? 'message-user-bubble w-fit max-w-full'
                  : 'message-float-card text-[var(--phosphor)]'
              }
            >
              {editing ? (
                <UserMessageEditor
                  initialContent={message.content}
                  disabled={Boolean(isStreaming)}
                  onSubmit={submitEdit}
                  onCancel={cancelEdit}
                />
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
                    <div className="flex flex-col gap-2 rounded-xl border border-[rgba(224,164,70,0.35)] bg-[rgba(224,164,70,0.1)] px-4 py-3">
                      <div className="flex items-center gap-2 text-[13px] font-semibold text-[var(--ui-accent)]">
                        <Shield className="h-3.5 w-3.5 text-[var(--ui-accent)]" aria-hidden />
                        Tools waiting for approval
                      </div>
                      <ul className="space-y-1.5 text-[13px] text-[var(--text-primary)]">
                        {message.pendingToolApprovals.map((item) => (
                          <li key={item.tool_id}>
                            <span>{item.name}</span>
                            <span className="text-[var(--phosphor-dim)]"> · {item.risk_class}</span>
                          </li>
                        ))}
                      </ul>
                      {onApproveTools ? (
                        <button
                          type="button"
                          onClick={() => onApproveTools(message.pendingToolApprovals!.map((item) => item.tool_id))}
                          className="self-start rounded-lg border border-[rgba(224,164,70,0.4)] bg-[rgba(224,164,70,0.18)] px-3.5 py-2 text-[12.5px] font-semibold text-[var(--phosphor-bright)] transition hover:bg-[rgba(224,164,70,0.28)]"
                        >
                          Approve and retry
                        </button>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              )}
            </div>
          )}

          {isUser && message.inputTokens !== undefined && !editing && (
            <span className="mt-1 text-xs tabular-nums text-[var(--phosphor-dim)]">
              {formatTokenCount(message.inputTokens)} tokens
            </span>
          )}

          {!isUser && <ReasoningPanel message={message} isStreaming={Boolean(isStreaming)} />}

          {showUserActions && (
            <div className="mt-1.5 flex flex-wrap items-center gap-3.5 pl-0.5 opacity-100 transition-opacity md:opacity-0 md:group-hover/message:opacity-100 md:group-focus-within/message:opacity-100">
              <button
                type="button"
                onClick={() => onCopy?.(message)}
                className="touch-target grid h-10 w-10 shrink-0 place-content-center rounded-md text-[var(--phosphor-dim)] transition hover:text-[var(--phosphor)] active:scale-[0.98] md:h-6 md:w-6"
                aria-label="Copy message"
                title="Copy markdown"
              >
                <Copy className="h-[15px] w-[15px]" strokeWidth={1.8} aria-hidden />
              </button>
              <button
                type="button"
                onClick={startEdit}
                className="touch-target grid h-10 w-10 shrink-0 place-content-center rounded-md text-[var(--phosphor-dim)] transition hover:text-[var(--phosphor)] active:scale-[0.98] md:h-6 md:w-6"
                aria-label="Edit message"
                title="Edit and resend"
              >
                <Pencil className="h-[15px] w-[15px]" strokeWidth={1.8} aria-hidden />
              </button>
            </div>
          )}

          {showAssistantActions && (
            <div className="mt-1.5 flex flex-wrap items-center gap-3.5 pl-0.5 opacity-100 transition-opacity md:opacity-0 md:group-hover/message:opacity-100 md:group-focus-within/message:opacity-100">
              <button
                type="button"
                onClick={() => onCopy?.(message)}
                className="touch-target grid h-10 w-10 shrink-0 place-content-center rounded-md text-[var(--phosphor-dim)] transition hover:text-[var(--phosphor)] active:scale-[0.98] md:h-6 md:w-6"
                aria-label="Copy message"
                title="Copy markdown"
              >
                <Copy className="h-[15px] w-[15px]" strokeWidth={1.8} aria-hidden />
              </button>
              <button
                type="button"
                onClick={() => onRegenerate?.(message)}
                className="touch-target grid h-10 w-10 shrink-0 place-content-center rounded-md text-[var(--phosphor-dim)] transition hover:text-[var(--phosphor)] active:scale-[0.98] md:h-6 md:w-6"
                aria-label="Regenerate"
                title="Regenerate"
              >
                <RefreshCw className="h-[15px] w-[15px]" strokeWidth={1.8} aria-hidden />
              </button>
              <button
                type="button"
                onClick={() => onFeedback?.(message, 'up')}
                className="touch-target grid h-10 w-10 shrink-0 place-content-center rounded-md text-[var(--phosphor-dim)] transition hover:text-[var(--phosphor)] active:scale-[0.98] md:h-6 md:w-6"
                aria-label="Thumbs up"
                title="Helpful"
              >
                <ThumbsUp className="h-[15px] w-[15px]" strokeWidth={1.8} aria-hidden />
              </button>
              <button
                type="button"
                onClick={() => onFeedback?.(message, 'down')}
                className="touch-target grid h-10 w-10 shrink-0 place-content-center rounded-md text-[var(--phosphor-dim)] transition hover:text-[var(--phosphor)] active:scale-[0.98] md:h-6 md:w-6"
                aria-label="Thumbs down"
                title="Not helpful"
              >
                <ThumbsDown className="h-[15px] w-[15px]" strokeWidth={1.8} aria-hidden />
              </button>
              {message.latencyMs !== undefined && (
                <span className="self-center text-xs tabular-nums text-[var(--phosphor-dim)]">
                  {formatLatency(message.latencyMs)}
                </span>
              )}
              {message.outputTokens !== undefined && (
                <span className="self-center text-xs tabular-nums text-[var(--phosphor-dim)]">
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
