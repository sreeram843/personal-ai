import { clsx } from 'clsx';
import { Info, LogOut, Moon, Sun } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import type { CurrentUser } from '../api';

function userInitials(user: CurrentUser): string {
  const name = (user.display_name || '').trim();
  if (name) {
    const parts = name.split(/\s+/).filter(Boolean);
    if (parts.length >= 2) {
      return `${parts[0][0] ?? ''}${parts[1][0] ?? ''}`.toUpperCase();
    }
    return name.slice(0, 2).toUpperCase();
  }

  const email = (user.email || '').trim();
  if (email) {
    return email.slice(0, 2).toUpperCase();
  }

  return 'U';
}

function userLabel(user: CurrentUser): string {
  return user.display_name?.trim() || user.email?.trim() || 'Signed in';
}

interface Props {
  user: CurrentUser;
  theme: 'light' | 'dark';
  onSetTheme: (theme: 'light' | 'dark') => void;
  onOpenAbout: () => void;
  onLogout: () => void;
}

export function UserMenu({ user, theme, onSetTheme, onOpenAbout, onLogout }: Props) {
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

  const toggleTheme = () => {
    onSetTheme(theme === 'dark' ? 'light' : 'dark');
  };

  return (
    <div ref={rootRef} className="relative mt-3 shrink-0 border-t border-[var(--ui-border)] pt-3">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="flex w-full items-center gap-2 rounded-lg px-1 py-1.5 text-left transition hover:bg-[var(--ui-hover)]"
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label={`Account menu for ${userLabel(user)}`}
      >
        <div className="grid h-8 w-8 shrink-0 place-content-center rounded-full bg-[var(--ui-bg-elevated)] text-[11px] font-semibold text-[var(--phosphor)]">
          {userInitials(user)}
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-xs font-semibold text-[var(--phosphor-bright)]">{userLabel(user)}</div>
          <div className="truncate text-[10px] text-[var(--phosphor-dim)]">{user.email || 'Account'}</div>
        </div>
      </button>

      {open && (
        <div
          role="menu"
          className="absolute bottom-full left-0 z-20 mb-2 w-full overflow-hidden rounded-xl border border-[var(--ui-border-strong)] bg-[var(--ui-panel-strong)] py-1 shadow-xl"
        >
          <div className="border-b border-[var(--ui-border)] px-3 py-2.5">
            <div className="truncate text-xs font-semibold text-[var(--phosphor-bright)]">{userLabel(user)}</div>
            {user.email && (
              <div className="truncate text-[10px] text-[var(--phosphor-dim)]">{user.email}</div>
            )}
          </div>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              onOpenAbout();
            }}
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--phosphor)] transition hover:bg-[var(--ui-bg-elevated)]"
          >
            <Info className="h-4 w-4 shrink-0" />
            About
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={toggleTheme}
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--phosphor)] transition hover:bg-[var(--ui-bg-elevated)]"
            aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {theme === 'dark' ? <Sun className="h-4 w-4 shrink-0" /> : <Moon className="h-4 w-4 shrink-0" />}
            {theme === 'dark' ? 'Light mode' : 'Dark mode'}
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              onLogout();
            }}
            className={clsx(
              'flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition hover:bg-[var(--ui-bg-elevated)]',
              'text-red-300',
            )}
          >
            <LogOut className="h-4 w-4 shrink-0" />
            Log out
          </button>
        </div>
      )}
    </div>
  );
}
