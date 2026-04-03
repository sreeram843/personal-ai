import { Check, Loader2, XCircle } from 'lucide-react';
import type { UploadStatus } from '../types';

interface Props {
  items: UploadStatus[];
}

export function UploadStatusList({ items }: Props) {
  if (items.length === 0) {
    return null;
  }

  return (
    <div className="mt-4 space-y-2" aria-live="polite" aria-label="Upload status updates">
      {items.map((item) => (
        <div
          key={item.id}
          className="flex items-center justify-between rounded-lg border border-[var(--ui-border)] bg-[var(--ui-panel)] px-4 py-2 text-sm text-[var(--phosphor)]"
        >
          <div>
            <div className="font-medium text-[var(--phosphor)]">{item.name}</div>
            {item.error && <div className="text-[11px] text-[var(--ui-danger)]">{item.error}</div>}
          </div>
          <div className="flex items-center gap-1 text-[var(--phosphor-dim)]">
            {item.status === 'uploading' && <Loader2 className="h-4 w-4 animate-spin text-[var(--phosphor)]" />}
            {item.status === 'success' && <Check className="h-4 w-4 text-[var(--phosphor)]" />}
            {item.status === 'error' && <XCircle className="h-4 w-4 text-[var(--ui-danger)]" />}
            <span className="text-[11px]">{item.status.toUpperCase()}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
