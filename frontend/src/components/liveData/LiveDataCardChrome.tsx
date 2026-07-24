import type { ReactNode } from 'react';

interface Props {
  title: string;
  badge?: ReactNode;
  footer?: ReactNode;
  children: ReactNode;
}

export function LiveDataCardChrome({ title, badge, footer, children }: Props) {
  return (
    <article className="live-data-card overflow-hidden rounded-2xl border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] shadow-[0_4px_16px_rgba(0,0,0,0.08)]">
      <header className="flex items-start justify-between gap-3 border-b border-[var(--ui-border)] px-4 py-3">
        <div className="min-w-0 text-sm font-semibold text-[var(--phosphor-bright)]">{title}</div>
        {badge ? <div className="shrink-0">{badge}</div> : null}
      </header>
      <div className="px-4 py-3.5">{children}</div>
      {footer ? (
        <footer className="border-t border-[var(--ui-border)] px-4 py-2 text-[11px] text-[var(--phosphor-dim)]">
          {footer}
        </footer>
      ) : null}
    </article>
  );
}

function FreshnessBadge({ live, delayed }: { live?: boolean; delayed?: boolean }) {
  if (live) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-[rgba(239,68,68,0.15)] px-2 py-0.5 text-[11px] font-medium text-[#f87171]">
        <span className="live-dot h-1.5 w-1.5 rounded-full bg-[#f87171]" aria-hidden />
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
