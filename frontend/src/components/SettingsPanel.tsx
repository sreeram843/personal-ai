import { clsx } from 'clsx';
import { X } from 'lucide-react';

interface Props {
  open: boolean;
  theme: 'light' | 'dark';
  onSetTheme: (theme: 'light' | 'dark') => void;
  onClose: () => void;
}

export function SettingsPanel({ open, theme, onSetTheme, onClose }: Props) {
  if (!open) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-end bg-black/30 p-3 backdrop-blur-[2px]"
      role="dialog"
      aria-modal="true"
      aria-label="Settings"
      onClick={onClose}
    >
      <div
        className="w-full max-w-xs rounded-xl border border-[var(--ui-border-strong)] bg-[var(--ui-panel-strong)] p-3 shadow-xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <div>
            <div className="text-xs uppercase tracking-[0.28em] text-[var(--phosphor-dim)]">Settings</div>
            <div className="text-sm font-semibold text-[var(--phosphor-bright)]">Appearance</div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="grid h-8 w-8 place-content-center rounded border border-[var(--ui-border)] transition hover:bg-[var(--ui-bg-elevated)]"
            aria-label="Close settings"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div>
          <div className="mb-1 text-[10px] uppercase tracking-[0.18em] text-[var(--phosphor-dim)]">Theme</div>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => onSetTheme('light')}
              className={clsx(
                'rounded border px-2 py-1.5 text-xs transition',
                theme === 'light'
                  ? 'border-[var(--ui-border-strong)] bg-[var(--ui-bg-elevated)] text-[var(--phosphor-bright)]'
                  : 'border-[var(--ui-border)] text-[var(--phosphor-dim)] hover:bg-[var(--ui-bg-elevated)]',
              )}
            >
              Light
            </button>
            <button
              type="button"
              onClick={() => onSetTheme('dark')}
              className={clsx(
                'rounded border px-2 py-1.5 text-xs transition',
                theme === 'dark'
                  ? 'border-[var(--ui-border-strong)] bg-[var(--ui-bg-elevated)] text-[var(--phosphor-bright)]'
                  : 'border-[var(--ui-border)] text-[var(--phosphor-dim)] hover:bg-[var(--ui-bg-elevated)]',
              )}
            >
              Dark
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
