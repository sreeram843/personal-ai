import { useMemo, useState } from 'react';
import { Copy, RefreshCw, ThumbsDown, ThumbsUp } from 'lucide-react';
import type { ChatMessage } from '../types';

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

  const structuredParagraphs = useMemo(() => {
    if (isUser) {
      return [] as string[];
    }
    return message.content
      .split('\n')
      .map((line) => line.trim())
      .filter((line) => line.length > 0)
      .slice(0, 5);
  }, [isUser, message.content]);

  return (
    <div className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'}`}>
      <article className={`flex w-full max-w-3xl gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
        <div className={`grid h-8 w-8 shrink-0 place-content-center rounded-full text-[11px] font-semibold ${isUser ? 'bg-[var(--ui-bg-elevated)] text-[var(--phosphor)] border border-[var(--ui-border)]' : 'bg-[var(--ui-focus)] text-white'}`}>
          {isUser ? 'U1' : 'AI'}
        </div>

        <div className={`min-w-0 ${isUser ? 'items-end' : 'items-start'} flex flex-col`}>
          <div
            className={`w-full rounded-2xl border p-4 text-[var(--phosphor)] ${
              isUser
                ? 'border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] rounded-br-md'
                : 'border-[var(--ui-border)] bg-[var(--ui-panel-strong)] rounded-bl-md'
            }`}
          >
            {isUser ? (
              <pre className="whitespace-pre-wrap break-words text-sm leading-relaxed text-[var(--phosphor)]">{message.content || (isStreaming ? 'Loading...' : '')}</pre>
            ) : (
              <div className="space-y-2">
                {structuredParagraphs.length > 1 ? (
                  <div className="space-y-2">
                    {structuredParagraphs.map((entry, index) => (
                      <div key={`${message.id}-card-${index}`} className="rounded-lg bg-[var(--ui-bg-elevated)] px-3 py-2 text-sm leading-relaxed">
                        {entry}
                      </div>
                    ))}
                  </div>
                ) : (
                  <pre className="whitespace-pre-wrap break-words text-sm leading-relaxed text-[var(--phosphor)]">{message.content || (isStreaming ? 'Loading...' : '')}</pre>
                )}
              </div>
            )}
          </div>

          <div className={`mt-1 text-[11px] text-[var(--phosphor-dim)] ${isUser ? 'text-right' : 'text-left'}`}>
            {new Date(message.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </div>

          {!isUser && (
            <div className="mt-2 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => onCopy?.(message)}
                className="inline-flex items-center gap-1 rounded-md border border-[var(--ui-border)] px-2 py-1 text-[11px] text-[var(--phosphor-dim)] transition hover:bg-[var(--ui-bg-elevated)]"
              >
                <Copy className="h-3.5 w-3.5" />
                Copy
              </button>
              <button
                type="button"
                onClick={() => onRegenerate?.(message)}
                className="inline-flex items-center gap-1 rounded-md border border-[var(--ui-border)] px-2 py-1 text-[11px] text-[var(--phosphor-dim)] transition hover:bg-[var(--ui-bg-elevated)]"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                Regenerate
              </button>
              <button
                type="button"
                onClick={() => onFeedback?.(message, 'up')}
                className="inline-flex items-center gap-1 rounded-md border border-[var(--ui-border)] px-2 py-1 text-[11px] text-[var(--phosphor-dim)] transition hover:bg-[var(--ui-bg-elevated)]"
                aria-label="Thumbs up"
              >
                <ThumbsUp className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={() => onFeedback?.(message, 'down')}
                className="inline-flex items-center gap-1 rounded-md border border-[var(--ui-border)] px-2 py-1 text-[11px] text-[var(--phosphor-dim)] transition hover:bg-[var(--ui-bg-elevated)]"
                aria-label="Thumbs down"
              >
                <ThumbsDown className="h-3.5 w-3.5" />
              </button>
            </div>
          )}

          {message.latencyMs !== undefined && (
            <div className="mt-1 text-[11px] text-[var(--phosphor-dim)]">{Math.round(message.latencyMs)} ms</div>
          )}

        {message.sources && message.sources.length > 0 && (
          <div className="mt-2 rounded border border-[var(--ui-border)] p-2 text-[11px] text-[var(--phosphor-dim)]">
            <div className="font-medium uppercase text-[var(--phosphor-bright)]">SOURCES</div>
            <ul className="mt-1 space-y-1">
              {message.sources.map((source) => {
                const displayName =
                  typeof source.metadata?.name === 'string' ? source.metadata.name : source.id;
                const pathValue = typeof source.metadata?.path === 'string' ? source.metadata.path : undefined;

                return (
                  <li key={source.id} className="rounded border border-[var(--ui-border)] p-1">
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
          <div className="mt-2 rounded border border-[var(--ui-border)] p-2 text-[11px] text-[var(--phosphor-dim)]">
            <div className="font-medium uppercase text-[var(--phosphor-bright)]">WORKFLOW TRACE</div>
            <div className="mt-1 text-[var(--phosphor)]">status {message.workflow.status}</div>
            <ul className="mt-1 space-y-1">
              {message.workflow.steps.map((step) => (
                <li key={step.id} className="rounded border border-[var(--ui-border)] p-1">
                  <div className="font-medium text-[var(--phosphor)]">{step.agent} · {step.title}</div>
                  <div className="text-[var(--phosphor-dim)]">{step.status}</div>
                  {step.summary && <div className="text-[var(--phosphor-dim)]">{step.summary}</div>}
                </li>
              ))}
            </ul>
          </div>
        )}

        {message.workflowMemoryEvents && message.workflowMemoryEvents.length > 0 && (
          <div className="mt-2 rounded border border-[var(--ui-border)] p-2 text-[11px] text-[var(--phosphor-dim)]">
            <div className="flex items-center justify-between gap-2">
              <div className="font-medium uppercase text-[var(--phosphor-bright)]">WORKFLOW MEMORY</div>
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
                  <li key={`${entry.phase}-${index}`} className="rounded border border-[var(--ui-border)] p-1">
                    <div className="font-medium text-[var(--phosphor)]">{entry.phase === 'read' ? 'loaded' : 'saved'}</div>
                    <div className="text-[var(--phosphor-dim)]">{entry.summary}</div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {message.workflowSourceEvents && message.workflowSourceEvents.length > 0 && (
          <div className="mt-2 rounded border border-[var(--ui-border)] p-2 text-[11px] text-[var(--phosphor-dim)]">
            <div className="flex items-center justify-between gap-2">
              <div className="font-medium uppercase text-[var(--phosphor-bright)]">STEP SOURCES</div>
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
                <li key={entry.key} className="rounded border border-[var(--ui-border)] p-1">
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
            <div className="mt-2 text-[11px] text-[var(--phosphor-dim)]">Streaming response...</div>
          )}
        </div>
      </article>
    </div>
  );
}
