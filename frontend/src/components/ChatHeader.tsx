import { clsx } from 'clsx';
import { MessageSquare, Settings, Share2 } from 'lucide-react';
import type { ConversationMode } from '../types';
import { CuraiLogo } from './CuraiLogo';
import type { CuraiLogoState } from './curaiLogoState';

interface Props {
  mode: ConversationMode;
  latency?: number;
  logoState: CuraiLogoState;
  conversationTitle: string;
  settingsOpen: boolean;
  onShareConversation: () => void;
  onToggleSettings: () => void;
}

const headerIconBtn =
  'grid h-8 w-8 shrink-0 place-content-center rounded-full border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)]/50 text-[var(--phosphor)] transition hover:border-[var(--ui-border-strong)] hover:bg-[var(--ui-bg-elevated)] active:scale-[0.99] dark:bg-transparent';

export function ChatHeader({
  mode,
  latency,
  logoState,
  conversationTitle,
  settingsOpen,
  onShareConversation,
  onToggleSettings,
}: Props) {
  const isSmart = mode === 'smart';
  const modeLabel = isSmart ? 'Smart chat' : 'Direct chat';

  const isBusy = logoState === 'thinking' || logoState === 'active' || logoState === 'error';

  const statusText =
    logoState === 'error'
      ? 'Unavailable'
      : latency !== undefined
        ? `Ready · ${Math.round(latency)} ms`
        : 'Ready';

  return (
    <header className="z-10 flex shrink-0 flex-col gap-1 border-b border-[var(--ui-border)] bg-[var(--ui-panel)] px-3 py-2 text-[var(--phosphor)] sm:px-4 md:flex-row md:items-center md:justify-between">
      <div className="flex min-w-0 items-center gap-2.5">
        <div
          className="grid h-8 w-8 shrink-0 place-content-center rounded-lg bg-[var(--ui-bg-elevated)] text-[var(--phosphor)] ring-1 ring-[var(--ui-border)]"
          title={modeLabel}
          aria-hidden
        >
          <MessageSquare className="h-4 w-4" />
        </div>
        <div className="min-w-0 truncate text-base font-semibold text-[var(--phosphor-bright)]">
          {conversationTitle}
        </div>
      </div>
      <div aria-live="polite" className="flex flex-wrap items-center gap-1.5 sm:justify-end">
        <div
          className={clsx(
            'inline-flex min-h-8 items-center rounded-full border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] text-sm text-[var(--phosphor-dim)]',
            isBusy ? 'px-2 py-1' : 'px-2.5 py-0.5',
          )}
        >
          {isBusy ? (
            <>
              <CuraiLogo state={logoState} size={28} />
              <span className="sr-only">
                {logoState === 'thinking' ? 'Thinking' : logoState === 'active' ? 'Responding' : 'Unavailable'}
              </span>
            </>
          ) : (
            <span className="tabular-nums text-[var(--phosphor)]">{statusText}</span>
          )}
        </div>
        <button
          type="button"
          onClick={onShareConversation}
          className={headerIconBtn}
          title="Copy conversation to clipboard"
          aria-label="Copy conversation to clipboard"
        >
          <Share2 className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          onClick={onToggleSettings}
          className={headerIconBtn}
          title={settingsOpen ? 'Close settings' : 'Open settings'}
          aria-label={settingsOpen ? 'Close settings' : 'Open settings'}
          aria-expanded={settingsOpen}
        >
          <Settings className="h-3.5 w-3.5" />
        </button>
      </div>
    </header>
  );
}
