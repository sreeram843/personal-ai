import type { ChatMessage } from '../types';

interface Props {
  message: ChatMessage;
  isStreaming?: boolean;
}

export function ChatMessageBubble({ message, isStreaming }: Props) {
  const isUser = message.role === 'user';
  const prefix = isUser ? '> USER' : '$ AI';

  return (
    <div className="flex w-full justify-start">
      <div className="max-w-3xl border border-[#004010] bg-[#001000] p-4 text-[#00ff41]">
        <div className="mb-1 text-xs uppercase text-[#00bb33]">{prefix} | {new Date(message.createdAt).toLocaleTimeString()}</div>
        <pre className="whitespace-pre-wrap break-words text-sm leading-relaxed text-[#00ff41]">{message.content || (isStreaming ? 'Loading...' : '')}</pre>

        {message.latencyMs !== undefined && (
          <div className="mt-2 text-[11px] text-[#00cc44]">{Math.round(message.latencyMs)} ms</div>
        )}

        {message.sources && message.sources.length > 0 && (
          <div className="mt-2 rounded border border-[#003800] p-2 text-[11px] text-[#00cc44]">
            <div className="font-medium uppercase text-[#00bb33]">SOURCES</div>
            <ul className="mt-1 space-y-1">
              {message.sources.map((source) => {
                const displayName =
                  typeof source.metadata?.name === 'string' ? source.metadata.name : source.id;
                const pathValue = typeof source.metadata?.path === 'string' ? source.metadata.path : undefined;

                return (
                  <li key={source.id} className="rounded border border-[#004010] p-1">
                    <div className="font-medium text-[#00ff41]">{displayName}</div>
                    {pathValue && <div className="text-[#00cc44]">{pathValue}</div>}
                    {source.score !== undefined && (
                      <div className="text-[#00cc44]">score {source.score.toFixed(3)}</div>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        {isStreaming && !isUser && (
          <div className="mt-2 text-[11px] text-[#00cc44]">[SYSTEM.LOG]: STREAMING IN PROGRESS...</div>
        )}
      </div>
    </div>
  );
}
