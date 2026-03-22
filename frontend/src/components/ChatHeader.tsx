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
    <header className="flex items-center justify-between border-b border-[#2f3d2f] bg-black/80 px-4 py-2 text-[var(--phosphor)]">
      <div className="flex items-center gap-3">
        <div className="text-[10px] uppercase tracking-widest text-[var(--phosphor-dim)]">{mode === 'rag' ? 'RAG CHAT' : 'STANDARD CHAT'}</div>
        <div className="text-sm font-semibold text-[var(--phosphor-bright)]">{model}</div>
      </div>
      <div className="flex items-center gap-3 text-xs text-[var(--phosphor)]">
        <div className="flex items-center gap-1">
          <Radio className="h-3.5 w-3.5 text-[var(--phosphor)]" />
          ONLINE
        </div>
        <div className="flex items-center gap-1">
          {isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin text-[var(--phosphor)]" /> : <span className="h-1.5 w-1.5 rounded-full bg-[var(--phosphor)]" />}
          {latency !== undefined ? `${Math.round(latency)} ms` : 'READY'}
        </div>
        <button
          type="button"
          onClick={onTogglePhosphor}
          className="rounded-md border border-[var(--phosphor-dim)] px-2 py-1 text-[10px] text-[var(--phosphor)] hover:bg-[#1b1b1b]"
        >
          {phosphor === 'green' ? 'GREEN' : 'AMBER'}
        </button>
        <button
          type="button"
          onClick={onToggleUI}
          className="rounded-md border border-[var(--phosphor-dim)] px-2 py-1 text-[10px] text-[var(--phosphor)] hover:bg-[#1b1b1b]"
        >
          {uiMode === 'classic' ? 'TERMINAL' : 'CLASSIC'}
        </button>
      </div>
    </header>
  );
}
