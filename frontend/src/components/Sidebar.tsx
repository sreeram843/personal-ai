import { clsx } from 'clsx';
import { Eye, FileUp, MessageCirclePlus, Sparkles, SunMoon } from 'lucide-react';
import type { ConversationMode } from '../types';

interface Props {
  mode: ConversationMode;
  onModeChange: (mode: ConversationMode) => void;
  onNewChat: () => void;
  onUpload: () => void;
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
  persona: string;
  personaOptions: string[];
  onPersonaChange: (name: string) => void;
  onPersonaPreview: () => void;
  personaDisabled?: boolean;
}

function formatLabel(value: string): string {
  return value
    .split('_')
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(' ');
}

export function Sidebar({
  mode,
  onModeChange,
  onNewChat,
  onUpload,
  theme,
  onToggleTheme,
  persona,
  personaOptions,
  onPersonaChange,
  onPersonaPreview,
  personaDisabled,
}: Props) {
  const menus = [
    {
      id: 'chat',
      label: 'Standard Chat',
      icon: MessageCirclePlus,
      description: 'Direct model responses',
    },
    {
      id: 'rag',
      label: 'RAG Chat',
      icon: Sparkles,
      description: 'Grounded in ingested docs',
    },
  ] as const;

  return (
    <aside className="flex h-full w-72 flex-col border-r border-gray-200 bg-gray-50/60 dark:border-zinc-800 dark:bg-zinc-950/60">
      <div className="flex items-center justify-between px-6 pb-6 pt-8">
        <div>
          <div className="text-xs uppercase tracking-widest text-emerald-500">Personal AI</div>
          <div className="text-lg font-semibold text-gray-900 dark:text-zinc-100">Assistant</div>
        </div>
        <button
          type="button"
          onClick={onToggleTheme}
          className="rounded-full border border-gray-200 p-2 text-gray-500 transition hover:bg-gray-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
          title="Toggle theme"
        >
          <SunMoon className="h-5 w-5" />
        </button>
      </div>

      <nav className="flex flex-col gap-2 px-4">
        {menus.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => onModeChange(item.id)}
            className={clsx(
              'flex items-center gap-3 rounded-2xl border border-transparent px-4 py-3 text-left transition',
              mode === item.id
                ? 'bg-white text-emerald-600 shadow dark:bg-zinc-900 dark:text-emerald-400'
                : 'text-gray-600 hover:bg-white dark:text-zinc-300 dark:hover:bg-zinc-900',
            )}
          >
            <item.icon className="h-5 w-5" />
            <div>
              <div className="font-medium">{item.label}</div>
              <div className="text-xs text-gray-500 dark:text-zinc-400">{item.description}</div>
            </div>
          </button>
        ))}
      </nav>

      <div className="mt-6 px-4">
        <div className="text-xs font-semibold uppercase tracking-wide text-gray-400 dark:text-zinc-500">
          Persona
        </div>
        <div className="mt-2 flex items-center gap-2">
          <select
            className="flex-1 rounded-xl border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 shadow-sm focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-200 disabled:cursor-not-allowed disabled:opacity-60 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
            value={persona}
            onChange={(event) => onPersonaChange(event.target.value)}
            disabled={personaDisabled || personaOptions.length === 0}
          >
            {personaOptions.map((option) => (
              <option key={option} value={option}>
                {formatLabel(option)}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={onPersonaPreview}
            className="grid h-10 w-10 place-content-center rounded-full border border-gray-200 text-gray-500 transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
            title="View persona"
            disabled={personaDisabled}
          >
            <Eye className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="mt-8 space-y-4 px-4">
        <button
          type="button"
          onClick={onNewChat}
          className="flex w-full items-center justify-center gap-2 rounded-2xl bg-emerald-500 py-3 text-sm font-semibold text-white shadow transition hover:bg-emerald-600"
        >
          <MessageCirclePlus className="h-4 w-4" />
          New Chat
        </button>
        <button
          type="button"
          onClick={onUpload}
          className="flex w-full items-center justify-center gap-2 rounded-2xl border border-dashed border-gray-300 py-3 text-sm font-semibold text-gray-600 transition hover:border-emerald-400 hover:bg-white dark:border-zinc-700 dark:text-zinc-200 dark:hover:border-emerald-400/70 dark:hover:bg-zinc-900"
        >
          <FileUp className="h-4 w-4" />
          Upload Docs
        </button>
      </div>

      <div className="mt-auto px-6 pb-6 text-xs text-gray-400 dark:text-zinc-500">
        <div>Mode: {mode === 'rag' ? 'Retrieval-Augmented' : 'Standard'} chat</div>
        <div>Theme: {theme}</div>
      </div>
    </aside>
  );
}
