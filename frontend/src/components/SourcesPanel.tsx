import { ChevronDown } from 'lucide-react';
import { useState } from 'react';
import type { RetrievedSource } from '../types';

interface Props {
  sources: RetrievedSource[];
}

function sourceTitle(source: RetrievedSource): string {
  const meta = source.metadata ?? {};
  for (const key of ['title', 'name', 'path', 'source', 'filename'] as const) {
    const value = meta[key];
    if (typeof value === 'string' && value.trim()) {
      return value.trim();
    }
  }
  return source.id || 'Source';
}

function sourceSubtitle(source: RetrievedSource): string | null {
  const meta = source.metadata ?? {};
  const path = typeof meta.path === 'string' ? meta.path.trim() : '';
  const title = sourceTitle(source);
  if (path && path !== title) {
    return path;
  }
  return null;
}

export function SourcesPanel({ sources }: Props) {
  const [open, setOpen] = useState(false);
  if (!sources.length) {
    return null;
  }

  return (
    <details
      open={open}
      onToggle={(event) => setOpen((event.target as HTMLDetailsElement).open)}
      className="mt-2 w-full overflow-hidden rounded-[10px] border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] text-sm text-[var(--phosphor-dim)]"
    >
      <summary className="flex cursor-pointer list-none items-center gap-2 px-3.5 py-2.5 text-[13px] text-[var(--text-primary)] marker:content-none">
        <ChevronDown
          className={`h-3.5 w-3.5 shrink-0 text-[var(--phosphor-dim)] transition-transform ${open ? 'rotate-180' : '-rotate-90'}`}
          aria-hidden
        />
        <span className="font-medium">Sources</span>
        <span className="text-[var(--phosphor-dim)]">({sources.length})</span>
      </summary>
      <ul className="space-y-2 border-t border-[var(--ui-border)] px-3.5 py-3">
        {sources.map((source, index) => {
          const title = sourceTitle(source);
          const subtitle = sourceSubtitle(source);
          const score =
            typeof source.score === 'number' && Number.isFinite(source.score)
              ? source.score.toFixed(2)
              : null;
          const excerpt = source.text?.trim();
          return (
            <li key={`${source.id}-${index}`} className="rounded-lg bg-[var(--ui-bg)] px-3 py-2">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="truncate text-[13px] font-medium text-[var(--phosphor-bright)]">{title}</div>
                  {subtitle ? (
                    <div className="truncate text-[11px] text-[var(--phosphor-dim)]">{subtitle}</div>
                  ) : null}
                </div>
                {score ? (
                  <span className="shrink-0 rounded-full bg-[var(--ui-bg-elevated)] px-2 py-0.5 text-[10px] tabular-nums text-[var(--phosphor-dim)]">
                    {score}
                  </span>
                ) : null}
              </div>
              {excerpt ? (
                <p className="mt-1.5 line-clamp-3 text-[12px] leading-relaxed text-[var(--phosphor-dim)]">
                  {excerpt}
                </p>
              ) : null}
            </li>
          );
        })}
      </ul>
    </details>
  );
}
