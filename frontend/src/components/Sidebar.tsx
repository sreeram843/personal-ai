import { clsx } from 'clsx';
import { FileUp, MessageCirclePlus, MessageSquare, Moon, Sparkles, Sun } from 'lucide-react';
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
  const iconButtonBase =
    'grid h-11 w-11 shrink-0 place-content-center rounded-xl border border-[#004010] text-[#00ff41] transition hover:bg-[#002000] sm:h-12 sm:w-12';

  const menus = [
    {
      id: 'chat',
      label: 'STANDARD CHAT',
      icon: MessageSquare,
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
    <aside className="border-b border-[#007f1f] bg-black/90 text-[#00ff41] transition-all duration-200 md:flex md:h-full md:w-20 md:flex-col md:border-b-0 md:border-r">
      <nav className="flex flex-row items-center gap-2 overflow-x-auto px-3 py-3 md:flex-col md:gap-3 md:px-3 md:pb-6 md:pt-8">
        <button
          type="button"
          onClick={onToggleTheme}
          title={theme === 'dark' ? 'Theme: Dark (click to switch to Light)' : 'Theme: Light (click to switch to Dark)'}
          aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
          className={iconButtonBase}
        >
          {theme === 'dark' ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
        </button>
        <button
          type="button"
          onClick={onToggleUI}
          className={clsx(iconButtonBase, 'text-xs tracking-[0.15em]')}
          title="Toggle UI mode (Terminal / Classic)"
          aria-label="Toggle UI mode"
        >
          UI
        </button>

        {menus.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => onModeChange(item.id)}
            title={`${item.label}: ${item.description}`}
            aria-label={item.label}
            className={clsx(
              iconButtonBase,
              'border-[#003800]',
              mode === item.id
                ? 'bg-[#002000] font-semibold text-[#a7ff7b]'
                : 'hover:bg-[#002000] text-[#00cc44]',
            )}
          >
            <item.icon className="h-5 w-5 text-[#00ff41]" />
          </button>
        ))}

        <button
          type="button"
          onClick={onNewChat}
          title="New session"
          aria-label="Start new chat"
          className={clsx(iconButtonBase, 'w-full bg-[#003000] hover:bg-[#004010]')}
        >
          <MessageCirclePlus className="h-4 w-4 text-[#00ff41]" />
        </button>
        <button
          type="button"
          onClick={onUpload}
          title="Upload docs"
          aria-label="Upload documents"
          className={clsx(iconButtonBase, 'w-full bg-[#001800] hover:bg-[#002200]')}
        >
          <FileUp className="h-4 w-4 text-[#00ff41]" />
        </button>
      </nav>

      <div className="hidden md:mt-auto md:block md:pb-6" />
    </aside>
  );
}
