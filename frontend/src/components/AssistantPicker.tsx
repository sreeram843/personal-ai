import { clsx } from 'clsx';
import { Bot, ChevronDown } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import type { AssistantSummary } from '../types';

interface Props {
  assistants: AssistantSummary[];
  selectedId: string;
  onSelect: (assistantId: string) => void;
  loading?: boolean;
}

export function AssistantPicker({ assistants, selectedId, onSelect, loading }: Props) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const selected = assistants.find((item) => item.id === selectedId) ?? assistants[0];

  useEffect(() => {
    if (!open) {
      return undefined;
    }
    const onPointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onPointerDown);
    return () => document.removeEventListener('mousedown', onPointerDown);
  }, [open]);

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="panel-rail__item panel-rail__item--select w-full"
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="inline-flex min-w-0 flex-1 items-center gap-2">
          <Bot className="panel-rail__item-icon h-4 w-4" />
          <span className="panel-rail__item-label truncate font-medium text-[var(--phosphor-bright)]">
            {loading ? 'Loading assistants…' : selected?.name ?? 'CurAI'}
          </span>
        </span>
        <ChevronDown className={clsx('h-4 w-4 shrink-0 opacity-70 transition', open ? 'rotate-180' : '')} />
      </button>
      {open ? (
        <div className="panel-rail__dropdown" role="listbox">
          {assistants.map((assistant) => (
            <button
              key={assistant.id}
              type="button"
              role="option"
              aria-selected={assistant.id === selectedId}
              disabled={!assistant.enabled}
              data-active={assistant.id === selectedId ? 'true' : 'false'}
              onClick={() => {
                onSelect(assistant.id);
                setOpen(false);
              }}
              className={clsx('panel-rail__dropdown-item', !assistant.enabled ? 'opacity-50' : '')}
            >
              <div className="text-sm font-medium">{assistant.name}</div>
              {assistant.description ? (
                <div className="mt-0.5 text-xs text-[var(--phosphor-dim)]">{assistant.description}</div>
              ) : null}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
