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
    <div className="mt-4 space-y-2">
      {items.map((item) => (
        <div
          key={item.id}
          className="flex items-center justify-between rounded-2xl border border-gray-200 bg-white px-4 py-2 text-sm shadow dark:border-zinc-700 dark:bg-zinc-800"
        >
          <div>
            <div className="font-medium text-gray-800 dark:text-zinc-100">{item.name}</div>
            {item.error && <div className="text-xs text-red-500">{item.error}</div>}
          </div>
          <div className="text-gray-400">
            {item.status === 'uploading' && <Loader2 className="h-4 w-4 animate-spin" />}
            {item.status === 'success' && <Check className="h-4 w-4 text-emerald-500" />}
            {item.status === 'error' && <XCircle className="h-4 w-4 text-red-500" />}
          </div>
        </div>
      ))}
    </div>
  );
}
