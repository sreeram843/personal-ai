import { Loader2, MessageCirclePlus, Settings, Share2 } from 'lucide-react';
import type { ConversationMode } from '../types';

interface Props {
  mode: ConversationMode;
  model: string;
  latency?: number;
  isLoading?: boolean;
  uiMode: 'classic' | 'terminal';
  conversationTitle: string;
  onShareConversation: () => void;
  onNewChat: () => void;
  onOpenSettings: () => void;
}

export function ChatHeader({
  mode,
  model,
  latency,
  isLoading,
  uiMode,
  conversationTitle,
  onShareConversation,
  onNewChat,
  onOpenSettings,
}: Props) {
  const modeLabel = mode === 'smart' ? 'Smart router · chat/rag/workflow' : 'Direct chat';
  const isClassicUI = uiMode === 'classic';

  if (!isClassicUI) {
    return (
      <header className="terminal-font flex flex-col gap-2 border-b border-[var(--ui-border)] bg-[var(--ui-panel)] px-4 py-2 text-[var(--phosphor)] sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="text-sm tracking-[0.18em] text-[var(--phosphor-bright)]">MACHINE_ALPHA_7</div>
          <div className="text-xs text-[var(--phosphor-dim)]">CHAT MODE ONLY</div>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <div className="rounded border border-[var(--ui-border)] px-2 py-1">{isLoading ? 'PROCESSING' : 'READY'}</div>
          <button
            type="button"
            onClick={onOpenSettings}
            className="rounded border border-[var(--ui-border)] px-2 py-1 transition hover:bg-[var(--ui-bg-elevated)]"
          >
            SETTINGS
          </button>
        </div>
      </header>
    );
  }

  return (
    <header className="flex flex-col gap-3 border-b border-[var(--ui-border)] bg-[color-mix(in_srgb,var(--ui-panel),transparent_4%)] px-4 py-3 text-[var(--phosphor)] backdrop-blur-[2px] sm:px-5 md:flex-row md:items-center md:justify-between">
      <div className="min-w-0">
        <div className="truncate text-sm font-semibold text-[var(--phosphor-bright)]">{conversationTitle}</div>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
          <div className="text-xs text-[var(--phosphor-dim)]">{modeLabel} · {model}</div>
          <div className="text-xs text-[var(--phosphor-dim)]">{uiMode === 'classic' ? 'Classic interface' : 'Terminal interface'}</div>
        </div>
      </div>
      <div aria-live="polite" className="flex flex-wrap items-center gap-2 text-[11px] text-[var(--phosphor)] sm:justify-end">
        <div className="rounded-full bg-[color-mix(in_srgb,var(--ui-focus),white_78%)] px-2.5 py-1 text-[10px] font-semibold text-[var(--ui-focus)]">
          {isLoading ? 'Thinking' : 'Ready'}
        </div>
        <div className="flex items-center gap-1 rounded-full border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] px-2.5 py-1">
          {isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin text-[var(--phosphor)]" /> : null}
          {latency !== undefined ? `${Math.round(latency)} ms` : 'Live'}
        </div>
        <button
          type="button"
          onClick={onNewChat}
          className="inline-flex items-center gap-1 rounded-full border border-[var(--ui-border)] px-2.5 py-1 text-[11px] text-[var(--phosphor)] transition hover:bg-[var(--ui-bg-elevated)]"
        >
          <MessageCirclePlus className="h-3.5 w-3.5" />
          New chat
        </button>
        <button
          type="button"
          onClick={onShareConversation}
          className="inline-flex items-center gap-1 rounded-full border border-[var(--ui-border)] px-2.5 py-1 text-[11px] text-[var(--phosphor)] transition hover:bg-[var(--ui-bg-elevated)]"
        >
          <Share2 className="h-3.5 w-3.5" />
          Share
        </button>
        <button
          type="button"
          onClick={onOpenSettings}
          className="inline-flex items-center gap-1 rounded-full border border-[var(--ui-border)] px-2.5 py-1 text-[11px] text-[var(--phosphor)] transition hover:bg-[var(--ui-bg-elevated)]"
        >
          <Settings className="h-3.5 w-3.5" />
          Settings
        </button>
      </div>
    </header>
  );
}
