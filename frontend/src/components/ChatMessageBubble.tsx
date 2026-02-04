import { clsx } from 'clsx';
import type { ChatMessage } from '../types';

interface Props {
  message: ChatMessage;
  isStreaming?: boolean;
}

export function ChatMessageBubble({ message, isStreaming }: Props) {
  const isUser = message.role === 'user';

  return (
    <div className={clsx('flex w-full', isUser ? 'justify-end' : 'justify-start')}>
      <div
        className={clsx(
          'max-w-3xl rounded-3xl px-4 py-3 shadow-sm transition-colors',
          isUser
            ? 'bg-emerald-500 text-white dark:bg-emerald-500'
            : 'bg-white text-gray-900 dark:bg-zinc-800 dark:text-zinc-100',
        )}
      >
        <div className="whitespace-pre-wrap leading-relaxed">{message.content}</div>
        {message.latencyMs !== undefined && (
          <div className="mt-2 text-xs text-emerald-100 dark:text-emerald-200/70">
            {Math.round(message.latencyMs)} ms
          </div>
        )}
        {message.sources && message.sources.length > 0 && (
          <div className="mt-3 space-y-1 text-xs text-gray-500 dark:text-zinc-300">
            <div className="font-medium uppercase tracking-wide text-gray-400 dark:text-zinc-400">
              Sources
            </div>
            <ul className="space-y-1">
              {message.sources.map((source) => {
                const displayName =
                  typeof source.metadata?.name === 'string' ? source.metadata.name : source.id;
                const pathValue = typeof source.metadata?.path === 'string' ? source.metadata.path : undefined;

                return (
                  <li
                    key={source.id}
                    className="rounded border border-gray-200 px-2 py-1 dark:border-zinc-700"
                  >
                    <div className="font-medium text-gray-800 dark:text-zinc-100">{displayName}</div>
                    {pathValue && (
                      <div className="text-[11px] text-gray-500 dark:text-zinc-400">{pathValue}</div>
                    )}
                    {source.score !== undefined && (
                      <div className="text-[11px] text-gray-400 dark:text-zinc-500">
                        score {source.score.toFixed(3)}
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        )}
        {isStreaming && !isUser && (
          <div className="mt-2 flex items-center gap-1 text-xs text-gray-400">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>
            Streaming...
          </div>
        )}
      </div>
    </div>
  );
}
