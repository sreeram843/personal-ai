import type { UploadStatus } from '../types';

interface Props {
  items: UploadStatus[];
}

const statusColor: Record<UploadStatus['status'], string> = {
  idle: 'text-[var(--phosphor-dim)]',
  uploading: 'text-[var(--phosphor-dim)]',
  success: 'text-[#6fcf97]',
  error: 'text-[var(--ui-danger)]',
};

export function UploadStatusList({ items }: Props) {
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
          className="flex items-center justify-between rounded-[10px] border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] px-3 py-2"
        >
          <div className="min-w-0 truncate text-[12.5px] text-[var(--text-primary)]">{item.name}</div>
          <span className={`shrink-0 pl-2 text-[11px] font-medium tracking-wide ${statusColor[item.status]}`}>
            {item.status === 'error' && item.error ? item.error : item.status.toUpperCase()}
          </span>
        </div>
      ))}
    </div>
  );
}
