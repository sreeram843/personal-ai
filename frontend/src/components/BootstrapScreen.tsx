import { Sparkles } from 'lucide-react';

interface Props {
  label?: string;
}

export function BootstrapScreen({ label = 'Loading…' }: Props) {
  return (
    <div className="classic-font flex min-h-screen items-center justify-center bg-[var(--ui-bg)] text-[var(--phosphor)]">
      <div className="flex flex-col items-center gap-3 text-center">
        <div className="grid h-11 w-11 place-content-center rounded-xl bg-[var(--ui-focus)] text-[var(--ui-accent-fg)] shadow-sm">
          <Sparkles className="h-5 w-5" />
        </div>
        <div className="text-sm text-[var(--phosphor-dim)]">{label}</div>
      </div>
    </div>
  );
}
