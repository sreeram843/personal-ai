import type { UploadStatus } from '../types';

interface Props {
  items: UploadStatus[];
  onRetry?: (item: UploadStatus) => void;
}

const statusColor: Record<UploadStatus['status'], string> = {
  idle: 'text-[var(--phosphor-dim)]',
  uploading: 'text-[var(--phosphor-dim)]',
  queued: 'text-[var(--ui-accent)]',
  processing: 'text-[var(--ui-accent)]',
  success: 'text-[#6fcf97]',
  error: 'text-[var(--ui-danger)]',
};

const statusLabel: Record<UploadStatus['status'], string> = {
  idle: 'IDLE',
  uploading: 'UPLOADING',
  queued: 'QUEUED',
  processing: 'PROCESSING',
  success: 'SUCCESS',
  error: 'ERROR',
};

export function UploadStatusList({ items, onRetry }: Props) {
  if (items.length === 0) {
    return null;
  }

  return (
    <div
      className="mx-auto mb-2 flex w-full max-w-[640px] flex-col gap-1.5"
      aria-live="polite"
      aria-label="Upload status updates"
    >
      {items.map((item) => (
        <div
          key={item.id}
          className="flex items-center justify-between gap-2 rounded-[10px] border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] px-3 py-2"
        >
          <div className="min-w-0 truncate text-[12.5px] text-[var(--text-primary)]">{item.name}</div>
          <div className="flex shrink-0 items-center gap-2 pl-2">
            <span className={`text-[11px] font-medium tracking-wide ${statusColor[item.status]}`}>
              {item.status === 'error' && item.error ? item.error : statusLabel[item.status]}
            </span>
            {item.status === 'error' && item.file && onRetry ? (
              <button
                type="button"
                className="touch-target rounded-md border border-[var(--ui-border)] px-2 text-[11px] font-medium text-[var(--phosphor)] hover:bg-[var(--ui-bg)]"
                onClick={() => onRetry(item)}
              >
                Retry
              </button>
            ) : null}
          </div>
        </div>
      ))}
    </div>
  );
}
