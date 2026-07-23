import { clsx } from 'clsx';
import { Menu, MessageSquare } from 'lucide-react';
import type { ConversationMode } from '../types';
import { CuraiLogo } from './CuraiLogo';
import type { CuraiLogoState } from './curaiLogoState';

interface Props {
  mode: ConversationMode;
  logoState: CuraiLogoState;
  conversationTitle: string;
  assistantName?: string;
  onOpenSidebar?: () => void;
}

const headerIconBtn =
  'touch-target grid h-10 w-10 shrink-0 place-content-center rounded-full border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)]/50 text-[var(--phosphor)] transition hover:border-[var(--ui-border-strong)] hover:bg-[var(--ui-bg-elevated)] active:scale-[0.99] dark:bg-transparent md:h-8 md:w-8';

export function ChatHeader({ mode, logoState, conversationTitle, assistantName, onOpenSidebar }: Props) {
  const modeLabel = mode === 'smart' ? 'Smart chat' : 'Direct chat';
  const isBusy = logoState === 'thinking' || logoState === 'active' || logoState === 'error';

  return (
    <header
      className="z-10 flex shrink-0 items-center justify-between gap-2 border-b border-[var(--ui-border)] bg-[var(--ui-panel)] px-3 py-2 text-[var(--phosphor)] sm:px-4"
      style={{ paddingTop: 'max(0.5rem, var(--safe-area-top))' }}
    >
      <div className="flex min-w-0 flex-1 items-center gap-2">
        {onOpenSidebar && (
          <button
            type="button"
            onClick={onOpenSidebar}
            className={clsx(headerIconBtn, 'md:hidden')}
            title="Open navigation"
            aria-label="Open navigation"
          >
            <Menu className="h-4 w-4" />
          </button>
        )}
        <div
          className="grid h-8 w-8 shrink-0 place-content-center rounded-lg bg-[var(--ui-bg-elevated)] text-[var(--phosphor)] ring-1 ring-[var(--ui-border)]"
          title={modeLabel}
          aria-hidden
        >
          <MessageSquare className="h-4 w-4" />
        </div>
        <div className="min-w-0 truncate">
          <div className="truncate font-display text-base font-semibold tracking-tight text-[var(--phosphor-bright)]">
            {conversationTitle}
          </div>
          {assistantName ? (
            <div className="type-meta truncate normal-case tracking-normal">Assistant: {assistantName}</div>
          ) : null}
        </div>
      </div>
      {isBusy && (
        <div aria-live="polite" className="inline-flex shrink-0 items-center rounded-full border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] px-2 py-1">
          <CuraiLogo state={logoState} size={28} />
          <span className="sr-only">
            {logoState === 'thinking' ? 'Thinking' : logoState === 'active' ? 'Responding' : 'Unavailable'}
          </span>
        </div>
      )}
    </header>
  );
}
