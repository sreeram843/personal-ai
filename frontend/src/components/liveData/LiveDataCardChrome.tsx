import type { ReactNode } from 'react';

interface Props {
  title: string;
  badge?: ReactNode;
  footer?: ReactNode;
  children: ReactNode;
}

export function LiveDataCardChrome({ title, badge, footer, children }: Props) {
  return (
    <article className="live-data-card overflow-hidden rounded-xl border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)]">
      <header className="flex items-start justify-between gap-3 border-b border-[var(--ui-border)] px-3.5 py-2.5">
        <div className="min-w-0 text-sm font-semibold text-[var(--phosphor-bright)]">{title}</div>
        {badge ? <div className="shrink-0">{badge}</div> : null}
      </header>
      <div className="px-3.5 py-3">{children}</div>
      {footer ? (
        <footer className="border-t border-[var(--ui-border)] px-3.5 py-2 text-[11px] text-[var(--phosphor-dim)]">
          {footer}
        </footer>
      ) : null}
    </article>
  );
}

function FreshnessBadge({ live, delayed }: { live?: boolean; delayed?: boolean }) {
  if (live) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-red-500/15 px-2 py-0.5 text-[11px] font-medium text-red-200">
        <span className="live-dot h-1.5 w-1.5 rounded-full bg-red-400" aria-hidden />
        Live
      </span>
    );
  }
  if (delayed) {
    return (
      <span className="rounded-full bg-[var(--ui-bg)] px-2 py-0.5 text-[11px] font-medium text-[var(--phosphor-dim)]">
        Delayed
      </span>
    );
  }
  return null;
}

export function LiveBadge() {
  return <FreshnessBadge live />;
}

export function DelayedBadge() {
  return <FreshnessBadge delayed />;
}

export { FreshnessBadge };
