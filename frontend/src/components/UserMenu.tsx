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
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="panel-rail__item w-full justify-start gap-2.5 px-2 py-2"
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label={`Account menu for ${userLabel(user)}`}
      >
        <div className="grid h-8 w-8 shrink-0 place-content-center rounded-full bg-[var(--ui-bg-elevated)] text-xs font-semibold text-[var(--phosphor)]">
          {userInitials(user)}
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-semibold text-[var(--phosphor-bright)]">{userLabel(user)}</div>
          <div className="truncate text-xs text-[var(--phosphor-dim)]">{user.email || 'Account'}</div>
        </div>
      </button>

      {open && (
        <div role="menu" className="panel-rail__menu panel-rail__menu--up">
          <div className="border-b border-[var(--ui-border)] px-3 py-2.5">
            <div className="truncate text-sm font-semibold text-[var(--phosphor-bright)]">{userLabel(user)}</div>
            {user.email && (
              <div className="truncate text-xs text-[var(--phosphor-dim)]">{user.email}</div>
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
            className="panel-rail__menu-item text-red-300 hover:bg-red-500/10"
          >
            <LogOut className="h-4 w-4 shrink-0" />
            Log out
          </button>
        </div>
      )}
    </div>
  );
}
