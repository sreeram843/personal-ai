import { clsx } from 'clsx';
import { MoreHorizontal, Pin, Pencil, Trash2 } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

export interface ConversationListItemData {
  id: string;
  title: string;
  updatedAt?: number;
  messageCount: number;
  pinned: boolean;
}

interface Props {
  item: ConversationListItemData;
  isActive: boolean;
  onSelect: (id: string) => void;
  onRename: (id: string, title: string) => void;
  onTogglePin: (id: string, pinned: boolean) => void;
  onDelete: (id: string, title: string) => void;
}

export function ConversationListItem({
  item,
  isActive,
  onSelect,
  onRename,
  onTogglePin,
  onDelete,
}: Props) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [isRenaming, setIsRenaming] = useState(false);
  const [draftTitle, setDraftTitle] = useState(item.title);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!menuOpen) {
      return undefined;
    }

    const handlePointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setMenuOpen(false);
        setIsRenaming(false);
        setDraftTitle(item.title);
      }
    };

    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [menuOpen, item.title]);

  useEffect(() => {
    setDraftTitle(item.title);
  }, [item.title]);

  useEffect(() => {
    if (isRenaming) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [isRenaming]);

  const commitRename = () => {
    const nextTitle = draftTitle.trim();
    setIsRenaming(false);
    setMenuOpen(false);
    if (!nextTitle || nextTitle === item.title) {
      setDraftTitle(item.title);
      return;
    }
    onRename(item.id, nextTitle);
  };

  return (
    <div ref={rootRef} className="group relative flex items-center gap-0.5">
      {isRenaming ? (
        <div className="min-w-0 flex-1 rounded-[10px] border border-[var(--ui-border-strong)] bg-[var(--ui-bg-elevated)] px-2.5 py-2">
          <input
            ref={inputRef}
            value={draftTitle}
            onChange={(event) => setDraftTitle(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault();
                commitRename();
              }
            }}
            onBlur={commitRename}
            className="w-full bg-transparent text-sm font-medium text-[var(--phosphor-bright)] outline-none"
            aria-label="Rename conversation"
          />
        </div>
      ) : (
        <button
          type="button"
          onClick={() => onSelect(item.id)}
          title={item.title}
          aria-current={isActive ? 'true' : undefined}
          data-active={isActive ? 'true' : 'false'}
          className="panel-rail__item panel-rail__item--stacked sidebar-conversation-item min-w-0 flex-1 pr-8"
        >
          <div className="flex min-w-0 w-full items-center gap-1.5">
            {item.pinned && (
              <Pin className="h-3 w-3 shrink-0 rotate-45 text-[var(--phosphor-dim)]" aria-hidden />
            )}
            <div
              className={clsx(
                'conversation-title-fade panel-rail__item-label min-w-0',
                isActive ? 'font-semibold text-[var(--phosphor-bright)]' : 'font-medium',
              )}
            >
              {item.title}
            </div>
          </div>
          <div className="type-meta mt-0.5">
            {item.updatedAt ? new Date(item.updatedAt).toLocaleDateString() : 'Today'} · {item.messageCount} messages
          </div>
        </button>
      )}

      {!isRenaming && (
        <div className="absolute right-1 top-1/2 z-10 -translate-y-1/2">
          <button
            type="button"
            onClick={() => setMenuOpen((prev) => !prev)}
            className={clsx(
              'conversation-menu-btn touch-target grid h-8 w-8 place-content-center rounded-lg text-[var(--phosphor-dim)] transition hover:bg-[var(--ui-bg-elevated)] hover:text-[var(--phosphor)]',
              menuOpen ? 'opacity-100' : 'opacity-100 md:opacity-0 md:group-hover:opacity-100 md:focus-visible:opacity-100',
            )}
            aria-label={`Actions for ${item.title}`}
            aria-expanded={menuOpen}
            aria-haspopup="menu"
          >
            <MoreHorizontal className="h-4 w-4" />
          </button>

          {menuOpen && (
            <div role="menu" className="panel-rail__menu">
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setMenuOpen(false);
                  onTogglePin(item.id, !item.pinned);
                }}
                className="panel-rail__menu-item"
              >
                <Pin className="h-4 w-4 shrink-0" />
                {item.pinned ? 'Unpin' : 'Pin'}
              </button>
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setMenuOpen(false);
                  setIsRenaming(true);
                }}
                className="panel-rail__menu-item"
              >
                <Pencil className="h-4 w-4 shrink-0" />
                Rename
              </button>
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setMenuOpen(false);
                  onDelete(item.id, item.title);
                }}
                className="panel-rail__menu-item text-red-300 hover:bg-red-500/10"
              >
                <Trash2 className="h-4 w-4 shrink-0" />
                Delete
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
