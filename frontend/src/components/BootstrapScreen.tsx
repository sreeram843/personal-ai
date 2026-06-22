import { CuraiLogo } from './CuraiLogo';

interface Props {
  label?: string;
  state?: 'thinking' | 'error';
}

export function BootstrapScreen({ label, state = 'thinking' }: Props) {
  return (
    <div className="classic-font flex min-h-screen items-center justify-center bg-[var(--ui-bg)] text-[var(--phosphor)]">
      <div className="flex flex-col items-center text-center">
        <CuraiLogo state={state} size={80} />
        {label ? <p className="mt-4 max-w-sm text-sm text-[var(--phosphor-dim)]">{label}</p> : null}
        <p className="sr-only">{label ?? 'Loading'}</p>
      </div>
    </div>
  );
}
