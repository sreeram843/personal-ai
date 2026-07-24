import { CheckCircle2, Circle, Moon, Sun } from 'lucide-react';

interface Props {
  theme: 'light' | 'dark';
  onSetTheme: (theme: 'light' | 'dark') => void;
}

const THEME_OPTIONS: Array<{
  value: 'light' | 'dark';
  label: string;
  hint: string;
  icon: typeof Sun;
}> = [
  {
    value: 'dark',
    label: 'Dark',
    hint: 'Dim panel with amber accents — easier at night.',
    icon: Moon,
  },
  {
    value: 'light',
    label: 'Light',
    hint: 'Bright canvas with the same amber accent.',
    icon: Sun,
  },
];

export function AppearancePanel({ theme, onSetTheme }: Props) {
  return (
    <section className="grid gap-2.5" role="radiogroup" aria-label="Color theme">
      {THEME_OPTIONS.map((option) => {
        const selected = theme === option.value;
        const Icon = option.icon;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={selected}
            data-selected={selected ? 'true' : 'false'}
            onClick={() => onSetTheme(option.value)}
            className="perm-card w-full text-left"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex min-w-0 items-start gap-3">
                <Icon className="mt-0.5 h-4 w-4 shrink-0 text-[var(--phosphor-dim)]" aria-hidden />
                <div className="min-w-0">
                  <div className="text-sm font-medium text-[var(--phosphor-bright)]">{option.label}</div>
                  <div className="mt-0.5 text-[11px] leading-relaxed text-[var(--phosphor-dim)]">{option.hint}</div>
                </div>
              </div>
              {selected ? (
                <CheckCircle2
                  className="perm-card-indicator h-4 w-4 shrink-0 text-[var(--ui-accent)]"
                  aria-hidden
                />
              ) : (
                <Circle
                  className="perm-card-indicator h-4 w-4 shrink-0 text-[var(--phosphor-dim)] opacity-50"
                  aria-hidden
                />
              )}
            </div>
          </button>
        );
      })}
    </section>
  );
}
