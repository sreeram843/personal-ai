import { Info, LogOut, Settings2 } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import type { CurrentUser } from '../api';
import { userInitials, userLabel } from '../utils/userDisplay';

interface Props {
  user: CurrentUser;
  onOpenAbout: () => void;
  onOpenSettings: () => void;
  onLogout: () => void;
}

export function UserMenu({ user, onOpenAbout, onOpenSettings, onLogout }: Props) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) {
      return undefined;
    }

    const handlePointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
      }
    };

    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [open]);

  return (
    <div ref={rootRef} className="relative border-t border-[var(--ui-border)] pt-4">
      <div className="flex items-center gap-1 rounded-lg px-1 py-1 transition hover:bg-[var(--ui-hover)]">
        <button
          type="button"
          onClick={() => onOpenSettings()}
          className="flex min-w-0 flex-1 items-center gap-2.5 rounded-lg px-1.5 py-1.5 text-left"
          aria-label={`Open settings for ${userLabel(user)}`}
        >
          <div className="grid h-[30px] w-[30px] shrink-0 place-content-center rounded-full bg-[var(--ui-accent)] text-[12px] font-bold text-[var(--ui-accent-fg)]">
            {userInitials(user)}
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-[13px] font-semibold text-[var(--phosphor-bright)]">{userLabel(user)}</div>
            <div className="truncate text-[11px] text-[var(--phosphor-dim)]">{user.email || 'Settings'}</div>
          </div>
        </button>
        <button
          type="button"
          className="grid h-7 w-7 shrink-0 place-content-center rounded-md text-[var(--phosphor-dim)] transition hover:bg-[var(--ui-bg-elevated)] hover:text-[var(--phosphor)]"
          aria-label="Account menu"
          aria-expanded={open}
          aria-haspopup="menu"
          onClick={() => setOpen((prev) => !prev)}
        >
          <Settings2 className="h-3.5 w-3.5" />
        </button>
      </div>

      {open && (
        <div role="menu" className="panel-rail__menu panel-rail__menu--up">
          <div className="border-b border-[var(--ui-border)] px-3.5 py-3">
            <div className="truncate text-[13px] font-semibold text-[var(--phosphor-bright)]">{userLabel(user)}</div>
            {user.email && (
              <div className="truncate text-[11.5px] text-[var(--phosphor-dim)]">{user.email}</div>
            )}
          </div>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              onOpenSettings();
            }}
            className="panel-rail__menu-item"
          >
            <Settings2 className="h-4 w-4 shrink-0" />
            Settings
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              onOpenAbout();
            }}
            className="panel-rail__menu-item"
          >
            <Info className="h-4 w-4 shrink-0" />
            About
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              onLogout();
            }}
            className="panel-rail__menu-item text-[var(--ui-danger)] hover:bg-[rgba(239,68,68,0.1)]"
          >
            <LogOut className="h-4 w-4 shrink-0" />
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
