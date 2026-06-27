import { LiveDataCardChrome } from './LiveDataCardChrome';

export function SkeletonLiveCard() {
  return (
    <LiveDataCardChrome title="Loading live data…">
      <div className="animate-pulse space-y-2.5" aria-hidden>
        <div className="h-4 w-2/3 rounded bg-[var(--ui-border)]" />
        <div className="h-3 w-full rounded bg-[var(--ui-border)]" />
        <div className="h-3 w-5/6 rounded bg-[var(--ui-border)]" />
      </div>
    </LiveDataCardChrome>
  );
}
