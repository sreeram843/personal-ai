import { useMemo, useState } from 'react';
import { Copy, RefreshCw, ThumbsDown, ThumbsUp } from 'lucide-react';
import type { ChatMessage } from '../types';
import { MessageContent } from './MessageContent';

interface Props {
  message: ChatMessage;
  isStreaming?: boolean;
  onCopy?: (message: ChatMessage) => void;
  onRegenerate?: (message: ChatMessage) => void;
  onFeedback?: (message: ChatMessage, value: 'up' | 'down') => void;
}

export function ChatMessageBubble({ message, isStreaming, onCopy, onRegenerate, onFeedback }: Props) {
  const isUser = message.role === 'user';
  const [memoryExpanded, setMemoryExpanded] = useState(false);
  const [sourcesExpanded, setSourcesExpanded] = useState(false);

  const groupedSourceEvents = useMemo(() => {
    if (!message.workflowSourceEvents || message.workflowSourceEvents.length === 0) {
      return [] as Array<{ key: string; agent: string; stepId: string; total: number; events: number }>;
    }

    const grouped = new Map<string, { key: string; agent: string; stepId: string; total: number; events: number }>();
    for (const entry of message.workflowSourceEvents) {
      const key = `${entry.agent}::${entry.stepId}`;
      const existing = grouped.get(key);
      if (existing) {
        existing.total += entry.count;
        existing.events += 1;
      } else {
        grouped.set(key, {
          key,
          agent: entry.agent,
          stepId: entry.stepId,
          total: entry.count,
          events: 1,
        });
      }
    }

    return Array.from(grouped.values());
  }, [message.workflowSourceEvents]);

  const memorySummary = useMemo(() => {
    if (!message.workflowMemoryEvents || message.workflowMemoryEvents.length === 0) {
      return { readCount: 0, writeCount: 0, latestRead: '', latestWrite: '' };
    }

    let latestRead = '';
    let latestWrite = '';
    let readCount = 0;
    let writeCount = 0;
    for (const entry of message.workflowMemoryEvents) {
      if (entry.phase === 'read') {
        readCount += 1;
        latestRead = entry.summary;
      } else {
        writeCount += 1;
        latestWrite = entry.summary;
      }
    }

    return { readCount, writeCount, latestRead, latestWrite };
  }, [message.workflowMemoryEvents]);

  return (
    <div className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'}`}>
      <article className={`flex w-full max-w-full ${isUser ? 'max-w-[85%] flex-row-reverse' : 'flex-row'} gap-2.5`}>
        <div
          className={`mt-0.5 grid h-7 w-7 shrink-0 place-content-center rounded-full text-[10px] font-semibold ${
            isUser
              ? 'bg-[var(--ui-bg-elevated)] text-[var(--phosphor-dim)] ring-1 ring-[var(--ui-border)]'
              : 'bg-[var(--ui-focus)] text-[var(--ui-accent-fg)]'
          }`}
        >
          {isUser ? 'U' : 'AI'}
        </div>

        <div className={`min-w-0 flex-1 ${isUser ? 'items-end' : 'items-start'} flex flex-col`}>
          <div
            className={
              isUser
                ? 'rounded-2xl rounded-br-md bg-[var(--ui-bg-elevated)] px-3.5 py-2.5 text-[var(--phosphor)] ring-1 ring-[var(--ui-border)]'
                : 'py-0.5 text-[var(--phosphor)]'
            }
          >
            <MessageContent content={message.content || (isStreaming ? 'Loading...' : '')} />
          </div>

          {!isUser && (
            <div className="mt-1 flex items-center gap-0.5">
              <button
                type="button"
                onClick={() => onCopy?.(message)}
                className="grid h-7 w-7 shrink-0 place-content-center rounded-md text-[var(--phosphor-dim)] transition hover:bg-[var(--ui-bg-elevated)] hover:text-[var(--phosphor)] active:scale-[0.98]"
                aria-label="Copy message"
                title="Copy"
              >
                <Copy className="h-3.5 w-3.5" aria-hidden />
              </button>
              <button
                type="button"
                onClick={() => onRegenerate?.(message)}
                className="grid h-7 w-7 shrink-0 place-content-center rounded-md text-[var(--phosphor-dim)] transition hover:bg-[var(--ui-bg-elevated)] hover:text-[var(--phosphor)] active:scale-[0.98]"
                aria-label="Regenerate"
                title="Regenerate"
              >
                <RefreshCw className="h-3.5 w-3.5" aria-hidden />
              </button>
              <button
                type="button"
                onClick={() => onFeedback?.(message, 'up')}
                className="grid h-7 w-7 shrink-0 place-content-center rounded-md text-[var(--phosphor-dim)] transition hover:bg-[var(--ui-bg-elevated)] hover:text-[var(--phosphor)] active:scale-[0.98]"
                aria-label="Thumbs up"
                title="Helpful"
              >
                <ThumbsUp className="h-3.5 w-3.5" aria-hidden />
              </button>
              <button
                type="button"
                onClick={() => onFeedback?.(message, 'down')}
                className="grid h-7 w-7 shrink-0 place-content-center rounded-md text-[var(--phosphor-dim)] transition hover:bg-[var(--ui-bg-elevated)] hover:text-[var(--phosphor)] active:scale-[0.98]"
                aria-label="Thumbs down"
                title="Not helpful"
              >
                <ThumbsDown className="h-3.5 w-3.5" aria-hidden />
              </button>
            </div>
          )}

          {message.latencyMs !== undefined && (
            <div className="mt-0.5 text-xs text-[var(--phosphor-dim)]">{Math.round(message.latencyMs)} ms</div>
          )}

        {message.sources && message.sources.length > 0 && (
          <div className="mt-2 rounded-lg border border-[var(--ui-border)] p-2 text-xs text-[var(--phosphor-dim)]">
            <div className="font-medium text-[var(--phosphor-bright)]">Sources</div>
            <ul className="mt-1 space-y-1">
              {message.sources.map((source) => {
                const displayName =
                  typeof source.metadata?.name === 'string' ? source.metadata.name : source.id;
                const pathValue = typeof source.metadata?.path === 'string' ? source.metadata.path : undefined;

                return (
                  <li key={source.id} className="rounded border border-[var(--ui-border)] p-1.5">
                    <div className="font-medium text-[var(--phosphor)]">{displayName}</div>
                    {pathValue && <div className="text-[var(--phosphor-dim)]">{pathValue}</div>}
                    {source.score !== undefined && (
                      <div className="text-[var(--phosphor-dim)]">score {source.score.toFixed(3)}</div>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        {message.workflow && message.workflow.steps.length > 0 && (
          <div className="mt-2 rounded-lg border border-[var(--ui-border)] p-2 text-xs text-[var(--phosphor-dim)]">
            <div className="font-medium text-[var(--phosphor-bright)]">Workflow trace</div>
            <div className="mt-1 text-[var(--phosphor)]">status {message.workflow.status}</div>
            <ul className="mt-1 space-y-1">
              {message.workflow.steps.map((step) => (
                <li key={step.id} className="rounded border border-[var(--ui-border)] p-1.5">
                  <div className="font-medium text-[var(--phosphor)]">{step.agent} · {step.title}</div>
                  <div className="text-[var(--phosphor-dim)]">{step.status}</div>
                  {step.summary && <div className="text-[var(--phosphor-dim)]">{step.summary}</div>}
                </li>
              ))}
            </ul>
          </div>
        )}

        {message.workflowMemoryEvents && message.workflowMemoryEvents.length > 0 && (
          <div className="mt-2 rounded-lg border border-[var(--ui-border)] p-2 text-xs text-[var(--phosphor-dim)]">
            <div className="flex items-center justify-between gap-2">
              <div className="font-medium text-[var(--phosphor-bright)]">Workflow memory</div>
              <button
                type="button"
                onClick={() => setMemoryExpanded((prev) => !prev)}
                className="rounded border border-[var(--ui-border)] px-2 py-0.5 text-[10px] uppercase text-[var(--phosphor-dim)] hover:bg-[var(--ui-bg-elevated)]"
              >
                {memoryExpanded ? 'collapse' : 'expand'}
              </button>
            </div>
            <div className="mt-1 text-[var(--phosphor)]">
              reads {memorySummary.readCount} | writes {memorySummary.writeCount}
            </div>
            {!memoryExpanded && (
              <div className="mt-1 text-[var(--phosphor-dim)]">
                {memorySummary.latestRead && <div>latest read: {memorySummary.latestRead}</div>}
                {memorySummary.latestWrite && <div>latest write: {memorySummary.latestWrite}</div>}
              </div>
            )}
            {memoryExpanded && (
              <ul className="mt-1 space-y-1">
                {message.workflowMemoryEvents.map((entry, index) => (
                  <li key={`${entry.phase}-${index}`} className="rounded border border-[var(--ui-border)] p-1.5">
                    <div className="font-medium text-[var(--phosphor)]">{entry.phase === 'read' ? 'loaded' : 'saved'}</div>
                    <div className="text-[var(--phosphor-dim)]">{entry.summary}</div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {message.workflowSourceEvents && message.workflowSourceEvents.length > 0 && (
          <div className="mt-2 rounded-lg border border-[var(--ui-border)] p-2 text-xs text-[var(--phosphor-dim)]">
            <div className="flex items-center justify-between gap-2">
              <div className="font-medium text-[var(--phosphor-bright)]">Step sources</div>
              <button
                type="button"
                onClick={() => setSourcesExpanded((prev) => !prev)}
                className="rounded border border-[var(--ui-border)] px-2 py-0.5 text-[10px] uppercase text-[var(--phosphor-dim)] hover:bg-[var(--ui-bg-elevated)]"
              >
                {sourcesExpanded ? 'collapse' : 'expand'}
              </button>
            </div>
            <div className="mt-1 text-[var(--phosphor)]">
              groups {groupedSourceEvents.length} | total events {message.workflowSourceEvents.length}
            </div>
            <ul className="mt-1 space-y-1">
              {(sourcesExpanded ? groupedSourceEvents : groupedSourceEvents.slice(0, 3)).map((entry) => (
                <li key={entry.key} className="rounded border border-[var(--ui-border)] p-1.5">
                  <div className="font-medium text-[var(--phosphor)]">{entry.agent} · {entry.stepId}</div>
                  <div className="text-[var(--phosphor-dim)]">{entry.total} source{entry.total === 1 ? '' : 's'} across {entry.events} event{entry.events === 1 ? '' : 's'}</div>
                </li>
              ))}
            </ul>
            {!sourcesExpanded && groupedSourceEvents.length > 3 && (
              <div className="mt-1 text-[var(--phosphor-dim)]">{groupedSourceEvents.length - 3} more groups hidden</div>
            )}
          </div>
        )}

          {isStreaming && !isUser && (
            <div className="mt-1 text-xs text-[var(--phosphor-dim)]">Streaming response...</div>
          )}
        </div>
      </article>
    </div>
  );
}
