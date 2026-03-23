import { Loader2, Radio } from 'lucide-react';
import type { ConversationMode } from '../types';

interface Props {
  mode: ConversationMode;
  model: string;
  latency?: number;
  isLoading?: boolean;
  uiMode: 'classic' | 'terminal';
  onToggleUI: () => void;
  phosphor: 'green' | 'amber';
  onTogglePhosphor: () => void;
}

export function ChatHeader({ mode, model, latency, isLoading, uiMode, onToggleUI, phosphor, onTogglePhosphor }: Props) {
  return (
    <header className="flex flex-col gap-3 border-b border-[#2f3d2f] bg-black/80 px-4 py-3 text-[var(--phosphor)] sm:px-5 md:flex-row md:items-center md:justify-between">
      <div className="min-w-0">
        <div className="text-[10px] uppercase tracking-[0.35em] text-[var(--phosphor-dim)]">{mode === 'rag' ? 'RAG CHAT' : 'STANDARD CHAT'}</div>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
          <div className="text-lg font-semibold leading-none text-[var(--phosphor-bright)] sm:text-xl">{model}</div>
          <div className="text-[11px] uppercase tracking-[0.25em] text-[var(--phosphor-dim)]">{uiMode === 'classic' ? 'Classic Interface' : 'Terminal Interface'}</div>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-[var(--phosphor)] sm:justify-end">
        <div className="flex items-center gap-1 rounded-full border border-[#173417] bg-[#051105]/70 px-2.5 py-1">
          <Radio className="h-3.5 w-3.5 text-[var(--phosphor)]" />
          ONLINE
        </div>
        <div className="flex items-center gap-1 rounded-full border border-[#173417] bg-[#051105]/70 px-2.5 py-1">
          {isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin text-[var(--phosphor)]" /> : <span className="h-1.5 w-1.5 rounded-full bg-[var(--phosphor)]" />}
          {latency !== undefined ? `${Math.round(latency)} ms` : 'READY'}
        </div>
        <button
          type="button"
          onClick={onTogglePhosphor}
          className="rounded-full border border-[var(--phosphor-dim)] px-3 py-1 text-[10px] tracking-[0.25em] text-[var(--phosphor)] transition hover:bg-[#1b1b1b]"
        >
          {phosphor === 'green' ? 'GREEN' : 'AMBER'}
        </button>
        <button
          type="button"
          onClick={onToggleUI}
          className="rounded-full border border-[var(--phosphor-dim)] px-3 py-1 text-[10px] tracking-[0.25em] text-[var(--phosphor)] transition hover:bg-[#1b1b1b]"
        >
          {uiMode === 'classic' ? 'TERMINAL' : 'CLASSIC'}
        </button>
      </div>
    </header>
  );
}
