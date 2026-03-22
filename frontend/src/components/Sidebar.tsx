import { clsx } from 'clsx';
import { FileUp, MessageCirclePlus, Sparkles, SunMoon } from 'lucide-react';
import type { ConversationMode } from '../types';

interface Props {
  mode: ConversationMode;
  onModeChange: (mode: ConversationMode) => void;
  onNewChat: () => void;
  onUpload: () => void;
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
  onToggleUI: () => void;
}

export function Sidebar({
  mode,
  onModeChange,
  onNewChat,
  onUpload,
  theme,
  onToggleTheme,
  onToggleUI,
}: Props) {
  const menus = [
    {
      id: 'chat',
      label: 'STANDARD CHAT',
      icon: MessageCirclePlus,
      description: 'DIRECT MODEL RESPONSES',
    },
    {
      id: 'rag',
      label: 'RAG CHAT',
      icon: Sparkles,
      description: 'GROUNDED IN INGESTED DOCS',
    },
  ] as const;

  return (
    <aside className="flex h-full w-20 flex-col border-r border-[#007f1f] bg-black/90 text-[#00ff41] transition-all duration-200">
      <div className="flex items-center justify-center px-4 pb-6 pt-8">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onToggleTheme}
            className="rounded-full border border-[#004010] p-2 text-[#00ff41] transition hover:bg-[#002000]"
            title="Toggle light or dark theme"
          >
            <SunMoon className="h-5 w-5" />
          </button>
          <button
            type="button"
            onClick={onToggleUI}
            className="rounded-md border border-[#004010] px-2 py-1 text-xs text-[#00ff41] transition hover:bg-[#002000]"
            title="Toggle between terminal and standard UI"
          >
            UI
          </button>
        </div>
      </div>

      <nav className="flex flex-col gap-2 px-3">
        {menus.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => onModeChange(item.id)}
            title={`${item.label}: ${item.description}`}
            className={clsx(
              'flex items-center rounded-lg border border-[#003800] py-3 text-left transition text-[#00ff41]',
              'justify-center px-2',
              mode === item.id
                ? 'bg-[#002000] font-semibold text-[#a7ff7b]'
                : 'hover:bg-[#002000] text-[#00cc44]',
            )}
          >
            <item.icon className="h-5 w-5 text-[#00ff41]" />
          </button>
        ))}
      </nav>

      <div className="mt-8 space-y-4 px-3">
        <button
          type="button"
          onClick={onNewChat}
          title="New session"
          className={clsx(
            'flex w-full items-center justify-center rounded-lg border border-[#004010] bg-[#003000] py-3 text-sm font-semibold text-[#00ff41] transition hover:bg-[#004010]',
            'px-2',
          )}
        >
          <MessageCirclePlus className="h-4 w-4 text-[#00ff41]" />
        </button>
        <button
          type="button"
          onClick={onUpload}
          title="Upload docs"
          className={clsx(
            'flex w-full items-center justify-center rounded-lg border border-[#004010] bg-[#001800] py-3 text-sm font-semibold text-[#00ff41] transition hover:bg-[#002200]',
            'px-2',
          )}
        >
          <FileUp className="h-4 w-4 text-[#00ff41]" />
        </button>
      </div>

      <div className="mt-auto px-3 pb-6 text-center text-[10px] text-[#00bb33]" title={`Mode: ${mode === 'rag' ? 'RAG' : 'STANDARD'} | Theme: ${theme}`}>
        STATUS
      </div>
    </aside>
  );
}
