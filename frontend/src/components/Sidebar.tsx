import { clsx } from 'clsx';
import { ChevronLeft, MessageCirclePlus, MessageSquare, PanelLeft, Sparkles, X } from 'lucide-react';
import type { CurrentUser } from '../api';
import type { ConversationMode } from '../types';
import { ConversationListItem, type ConversationListItemData } from './ConversationListItem';
import { CuraiLogo } from './CuraiLogo';
import { UserMenu } from './UserMenu';

interface Props {
  mode: ConversationMode;
  onModeChange: (mode: ConversationMode) => void;
  onNewChat: () => void;
  conversations: ConversationListItemData[];
  activeConversationId: string;
  onSelectConversation: (id: string) => void;
  onRenameConversation: (id: string, title: string) => void;
  onTogglePinConversation: (id: string, pinned: boolean) => void;
  onDeleteConversation: (id: string, title: string) => void;
  sidebarCollapsed: boolean;
  onToggleSidebarCollapsed: () => void;
  theme: 'light' | 'dark';
  onSetTheme: (theme: 'light' | 'dark') => void;
  user: CurrentUser;
  onOpenAbout: () => void;
  onLogout: () => void;
  mobileOpen?: boolean;
  onMobileClose?: () => void;
}

export function Sidebar({
  mode,
  onModeChange,
  onNewChat,
  conversations,
  activeConversationId,
  onSelectConversation,
  onRenameConversation,
  onTogglePinConversation,
  onDeleteConversation,
  sidebarCollapsed,
  onToggleSidebarCollapsed,
  theme,
  onSetTheme,
  user,
  onOpenAbout,
  onLogout,
  mobileOpen = false,
  onMobileClose,
}: Props) {
  const menus = [
    { id: 'chat' as const, label: 'Chat', icon: MessageSquare },
    { id: 'smart' as const, label: 'Smart', icon: Sparkles },
  ];

  const pinned = conversations.filter((item) => item.pinned);
  const recent = conversations.filter((item) => !item.pinned);

  const handleDelete = (id: string, title: string) => {
    const confirmed = window.confirm(`Delete "${title}"? This cannot be undone.`);
    if (confirmed) {
      onDeleteConversation(id, title);
    }
  };

  const renderConversationGroup = (items: ConversationListItemData[]) => (
    <div className="space-y-1">
      {items.map((item) => (
        <ConversationListItem
          key={item.id}
          item={item}
          isActive={item.id === activeConversationId}
          onSelect={onSelectConversation}
          onRename={onRenameConversation}
          onTogglePin={onTogglePinConversation}
          onDelete={handleDelete}
        />
      ))}
    </div>
  );

  if (sidebarCollapsed) {
    return (
      <aside className="relative hidden min-h-0 border-b border-[var(--ui-border)] bg-[var(--ui-panel)] md:flex md:h-full md:w-[52px] md:min-w-[52px] md:max-w-[52px] md:flex-col md:border-b-0 md:border-r">
        <div className="flex h-full min-h-[3rem] items-start justify-center py-3 md:min-h-0 md:pt-4">
          <button
            type="button"
            onClick={onToggleSidebarCollapsed}
            className="grid h-9 w-9 place-content-center rounded-lg border border-[var(--ui-border)] text-[var(--phosphor)] transition hover:bg-[var(--ui-bg-elevated)] focus-visible:ring-2 focus-visible:ring-[var(--ui-focus)]"
            title="Expand sidebar"
            aria-label="Expand sidebar"
          >
            <PanelLeft className="h-4 w-4" />
          </button>
        </div>
      </aside>
    );
  }

  return (
    <>
      {mobileOpen && (
        <button
          type="button"
          className="fixed inset-0 z-30 bg-black/40 md:hidden"
          aria-label="Dismiss menu overlay"
          onClick={onMobileClose}
        />
      )}
      <aside
        className={clsx(
          'fixed inset-y-0 left-0 z-40 flex w-[min(100vw-2.5rem,280px)] min-h-0 flex-col border-r border-[var(--ui-border)] bg-[var(--ui-panel)] text-[var(--phosphor)] shadow-xl transition-transform duration-200 ease-out md:relative md:z-auto md:w-[260px] md:min-w-[260px] md:translate-x-0 md:shadow-none',
          mobileOpen ? 'translate-x-0' : '-translate-x-full max-md:invisible max-md:pointer-events-none md:translate-x-0',
        )}
        style={{
          paddingTop: 'var(--safe-area-top)',
          paddingBottom: 'var(--safe-area-bottom)',
        }}
      >
      <div className="flex h-full min-h-0 w-full min-w-0 flex-col px-3 py-3 md:px-3.5 md:py-3.5">
        <div className="mb-3.5 flex shrink-0 items-center gap-2.5">
          <CuraiLogo state="idle" size={36} />
          <div className="curai-sidebar-wordmark min-w-0 flex-1 text-lg font-semibold tracking-tight text-[var(--phosphor-bright)]">
            CurAI
          </div>
          <button
            type="button"
            onClick={onMobileClose}
            className="touch-target grid h-10 w-10 shrink-0 place-content-center rounded border border-[var(--ui-border)] text-[var(--phosphor)] transition hover:bg-[var(--ui-bg-elevated)] md:hidden"
            title="Close navigation"
            aria-label="Close navigation"
          >
            <X className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={onToggleSidebarCollapsed}
            className="hidden h-8 w-8 shrink-0 place-content-center rounded border border-[var(--ui-border)] text-[var(--phosphor)] transition hover:bg-[var(--ui-bg-elevated)] md:grid"
            title="Collapse sidebar"
            aria-label="Collapse sidebar"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
        </div>

        <button
          type="button"
          onClick={onNewChat}
          title="New conversation"
          aria-label="Start new conversation"
          className="mb-3 flex w-full shrink-0 items-center gap-2 rounded-lg border border-[var(--ui-border)] bg-[var(--ui-panel-strong)] px-3 py-2 text-sm font-medium text-[var(--phosphor)] transition hover:border-[var(--ui-border-strong)] hover:bg-[var(--ui-bg-elevated)] active:scale-[0.99]"
        >
          <MessageCirclePlus className="h-4 w-4" />
          New conversation
        </button>

        <div className="mb-1.5 text-[10px] uppercase tracking-[0.22em] text-[var(--phosphor-dim)]">Mode</div>
        <div className="mb-3 grid grid-cols-2 gap-1.5">
          {menus.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => onModeChange(item.id)}
              title={item.label}
              aria-label={item.label}
              className={clsx(
                'flex min-h-[44px] items-center justify-center gap-1 rounded-md border px-2 py-2 text-xs font-medium transition md:min-h-0 md:py-1.5',
                mode === item.id
                  ? 'border-[var(--ui-border-strong)] bg-[var(--ui-bg-elevated)] text-[var(--phosphor-bright)]'
                  : 'border-[var(--ui-border)] text-[var(--phosphor-dim)] hover:bg-[var(--ui-bg-elevated)]',
              )}
            >
              <item.icon className="h-3.5 w-3.5" />
              {item.label}
            </button>
          ))}
        </div>

        <div className="sidebar-conversation-list min-h-0 flex-1 space-y-3 overflow-y-auto px-1 py-0.5 pr-2">
          {pinned.length > 0 && (
            <div>
              <div className="mb-1.5 text-[10px] uppercase tracking-[0.22em] text-[var(--phosphor-dim)]">Pinned</div>
              {renderConversationGroup(pinned)}
            </div>
          )}
          <div>
            <div className="mb-1.5 text-[10px] uppercase tracking-[0.22em] text-[var(--phosphor-dim)]">
              {pinned.length > 0 ? 'Recent' : 'Recent'}
            </div>
            {recent.length > 0 ? (
              renderConversationGroup(recent)
            ) : pinned.length === 0 ? (
              <div className="rounded-lg px-2.5 py-3 text-xs text-[var(--phosphor-dim)]">No conversations yet</div>
            ) : null}
          </div>
        </div>

        <UserMenu user={user} theme={theme} onSetTheme={onSetTheme} onOpenAbout={onOpenAbout} onLogout={onLogout} />
      </div>
    </aside>
    </>
  );
}
