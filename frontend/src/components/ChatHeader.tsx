import { Loader2, Radio } from 'lucide-react';
import type { ConversationMode } from '../types';

interface Props {
  mode: ConversationMode;
  model: string;
  latency?: number;
  isLoading?: boolean;
  persona: string;
}

function labelPersona(value: string): string {
  return value
    .split('_')
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(' ');
}

export function ChatHeader({ mode, model, latency, isLoading, persona }: Props) {
  return (
    <header className="flex items-center justify-between border-b border-gray-200 bg-white/80 px-6 py-4 dark:border-zinc-800 dark:bg-zinc-900/80">
      <div>
        <div className="text-xs uppercase tracking-widest text-gray-400">{mode === 'rag' ? 'RAG chat' : 'Standard chat'}</div>
        <div className="text-xl font-semibold text-gray-900 dark:text-zinc-100">{model}</div>
        <div className="text-xs text-gray-500 dark:text-zinc-400">Persona: {labelPersona(persona)}</div>
      </div>
      <div className="flex items-center gap-3 text-sm text-gray-500 dark:text-zinc-300">
        <div className="flex items-center gap-1">
          <Radio className="h-4 w-4 text-emerald-500" />
          Live
        </div>
        <div className="flex items-center gap-1">
          {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <span className="h-2 w-2 rounded-full bg-emerald-500" />}
          {latency !== undefined ? `${Math.round(latency)} ms` : 'ready'}
        </div>
      </div>
    </header>
  );
}
