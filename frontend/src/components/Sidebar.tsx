import { clsx } from 'clsx';
import { ChevronLeft, PanelLeft, Plus, X } from 'lucide-react';
import { useState } from 'react';
import type { CurrentUser } from '../api';
import { groupConversationsByDate } from '../utils/conversationGroups';
import { ConfirmDialog } from './ConfirmDialog';
import { ConversationListItem, type ConversationListItemData } from './ConversationListItem';
import { CuraiLogo } from './CuraiLogo';
import { UserMenu } from './UserMenu';

interface Props {
  onNewChat: () => void;
  conversations: ConversationListItemData[];
  activeConversationId: string;
  onSelectConversation: (id: string) => void;
  onRenameConversation: (id: string, title: string) => void;
  onTogglePinConversation: (id: string, pinned: boolean) => void;
  onDeleteConversation: (id: string, title: string) => void;
  sidebarCollapsed: boolean;
  onToggleSidebarCollapsed: () => void;
  user: CurrentUser;
  onOpenAbout: () => void;
  onOpenSettings: () => void;
  onLogout: () => void;
  mobileOpen?: boolean;
  onMobileClose?: () => void;
}

export function Sidebar({
  onNewChat,
  conversations,
  activeConversationId,
  onSelectConversation,
  onRenameConversation,
  onTogglePinConversation,
  onDeleteConversation,
  sidebarCollapsed,
  onToggleSidebarCollapsed,
  user,
  onOpenAbout,
  onOpenSettings,
  onLogout,
  mobileOpen = false,
  onMobileClose,
}: Props) {
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; title: string } | null>(null);
  const pinned = conversations.filter((item) => item.pinned);
  const recentGroups = groupConversationsByDate(conversations.filter((item) => !item.pinned));

  const handleDelete = (id: string, title: string) => {
    setDeleteTarget({ id, title });
  };

  const confirmDelete = () => {
    if (!deleteTarget) {
      return;
    }
    onDeleteConversation(deleteTarget.id, deleteTarget.title);
    setDeleteTarget(null);
  };

  const renderConversationGroup = (items: ConversationListItemData[]) => (
    <ul className="panel-rail__list">
      {items.map((item) => (
        <li key={item.id}>
          <ConversationListItem
            item={item}
            isActive={item.id === activeConversationId}
            onSelect={onSelectConversation}
            onRename={onRenameConversation}
            onTogglePin={onTogglePinConversation}
            onDelete={handleDelete}
          />
        </li>
      ))}
    </ul>
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
      <ConfirmDialog
        open={deleteTarget !== null}
        title="Delete conversation"
        message={
          <>
            Delete &ldquo;{deleteTarget?.title}&rdquo;? This cannot be undone.
          </>
        }
        confirmLabel="Delete"
        tone="danger"
        onConfirm={confirmDelete}
        onCancel={() => setDeleteTarget(null)}
      />
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
          'panel-rail fixed inset-y-0 left-0 z-40 w-[min(100vw-2.5rem,270px)] min-h-0 shadow-xl transition-transform duration-200 ease-out md:relative md:z-auto md:w-[270px] md:min-w-[270px] md:translate-x-0 md:shadow-none',
          mobileOpen ? 'translate-x-0' : '-translate-x-full max-md:invisible max-md:pointer-events-none md:translate-x-0',
        )}
        style={{
          paddingTop: 'var(--safe-area-top)',
          paddingBottom: 'var(--safe-area-bottom)',
        }}
        aria-label="Main navigation"
      >
        <div className="panel-rail__inner">
          <div className="panel-rail__header">
            <div className="grid h-8 w-8 shrink-0 place-content-center rounded-lg bg-[var(--ui-bg-elevated)]">
              <CuraiLogo state="idle" size={19} />
            </div>
            <div className="curai-sidebar-wordmark font-display text-[16.5px] font-semibold tracking-[0.2px] text-[var(--phosphor-bright)]">
              CurAI
            </div>
            <button
              type="button"
              onClick={onMobileClose}
              className="touch-target ml-auto grid h-10 w-10 shrink-0 place-content-center rounded-lg border border-[var(--ui-border)] text-[var(--phosphor)] transition hover:bg-[var(--ui-bg-elevated)] md:hidden"
              title="Close navigation"
              aria-label="Close navigation"
            >
              <X className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={onToggleSidebarCollapsed}
              className="ml-auto hidden h-8 w-8 shrink-0 place-content-center rounded-lg border border-[var(--ui-border)] text-[var(--phosphor)] transition hover:bg-[var(--ui-bg-elevated)] md:grid"
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
            className="panel-rail__cta"
          >
            <Plus className="h-[15px] w-[15px] shrink-0 stroke-[2.5]" aria-hidden />
            New conversation
          </button>

          <div className="panel-rail__scroll">
            {pinned.length > 0 && (
              <div className="panel-rail__group">
                <div className="panel-rail__eyebrow type-eyebrow">Pinned</div>
                {renderConversationGroup(pinned)}
              </div>
            )}
            {recentGroups.length > 0 ? (
              recentGroups.map((group) => (
                <div key={group.id} className="panel-rail__group">
                  <div className="panel-rail__eyebrow type-eyebrow">{group.label}</div>
                  {renderConversationGroup(group.items)}
                </div>
              ))
            ) : pinned.length === 0 ? (
              <div className="panel-rail__empty">No conversations yet</div>
            ) : null}
          </div>

          <div className="panel-rail__footer">
            <UserMenu
              user={user}
              onOpenAbout={onOpenAbout}
              onOpenSettings={onOpenSettings}
              onLogout={onLogout}
            />
          </div>
        </div>
      </aside>
    </>
  );
}
