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
          className="flex items-center justify-between rounded-lg border border-[#004010] bg-[#001000] px-4 py-2 text-sm text-[#00ff41]"
        >
          <div>
            <div className="font-medium text-[#00ff41]">{item.name}</div>
            {item.error && <div className="text-[11px] text-[#ff5555]">{item.error}</div>}
          </div>
          <div className="flex items-center gap-1 text-[#00cc44]">
            {item.status === 'uploading' && <Loader2 className="h-4 w-4 animate-spin text-[#00ff41]" />}
            {item.status === 'success' && <Check className="h-4 w-4 text-[#00ff41]" />}
            {item.status === 'error' && <XCircle className="h-4 w-4 text-[#ff5555]" />}
            <span className="text-[11px]">{item.status.toUpperCase()}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
