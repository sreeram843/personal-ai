import { clsx } from 'clsx';
import { ChevronLeft, MessageCirclePlus, MessageSquare, PanelLeft, Sparkles } from 'lucide-react';
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
  user: CurrentUser;
  onOpenAbout: () => void;
  onLogout: () => void;
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
  user,
  onOpenAbout,
  onLogout,
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
      <aside className="relative flex min-h-0 border-b border-[var(--ui-border)] bg-[var(--ui-panel)] md:h-full md:w-[52px] md:min-w-[52px] md:max-w-[52px] md:flex-col md:border-b-0 md:border-r">
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
    <aside className="relative flex min-h-0 border-b border-[var(--ui-border)] bg-[var(--ui-panel)] text-[var(--phosphor)] transition-all duration-200 md:h-full md:w-[260px] md:min-w-[260px] md:flex-col md:border-b-0 md:border-r">
      <div className="flex h-full min-h-0 w-full min-w-0 flex-col px-3 py-3 md:px-3.5 md:py-3.5">
        <div className="mb-3.5 flex shrink-0 items-center gap-2.5">
          <CuraiLogo state="idle" size={36} />
          <div className="curai-sidebar-wordmark min-w-0 flex-1 text-lg font-semibold tracking-tight text-[var(--phosphor-bright)]">
            CurAI
          </div>
          <button
            type="button"
            onClick={onToggleSidebarCollapsed}
            className="grid h-8 w-8 shrink-0 place-content-center rounded border border-[var(--ui-border)] text-[var(--phosphor)] transition hover:bg-[var(--ui-bg-elevated)]"
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
                'flex items-center justify-center gap-1 rounded-md border px-2 py-1.5 text-xs font-medium transition',
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

        <div className="sidebar-conversation-list min-h-0 flex-1 space-y-3 overflow-y-auto px-1 py-0.5 pr-2 max-h-[min(46vh,320px)] md:max-h-none">
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

        <UserMenu user={user} theme={theme} onOpenAbout={onOpenAbout} onLogout={onLogout} />
      </div>
    </aside>
  );
}
