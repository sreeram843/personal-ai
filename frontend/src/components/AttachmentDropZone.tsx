import { useCallback, useState, type DragEvent, type ReactNode } from 'react';
import { Paperclip } from 'lucide-react';
import { isAcceptedFile } from '../utils/attachmentFiles';

interface Props {
  disabled?: boolean;
  onFiles: (files: FileList | File[]) => void;
  children: ReactNode;
}

export function AttachmentDropZone({ disabled, onFiles, children }: Props) {
  const [isDragging, setIsDragging] = useState(false);

  const handleDragEnter = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      if (disabled) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      setIsDragging(true);
    },
    [disabled],
  );

  const handleDragLeave = useCallback((event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    if (event.currentTarget.contains(event.relatedTarget as Node | null)) {
      return;
    }
    setIsDragging(false);
  }, []);

  const handleDragOver = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      if (disabled) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
    },
    [disabled],
  );

  const handleDrop = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      event.stopPropagation();
      setIsDragging(false);
      if (disabled || !event.dataTransfer.files?.length) {
        return;
      }
      const accepted = Array.from(event.dataTransfer.files).filter(isAcceptedFile);
      if (accepted.length > 0) {
        onFiles(accepted);
      }
    },
    [disabled, onFiles],
  );

  return (
    <div
      className={`composer-drop-zone relative ${isDragging ? 'composer-drop-zone--active' : ''}`}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      {isDragging && (
        <div
          className="composer-drop-overlay pointer-events-none absolute inset-0 z-10 flex items-center justify-center rounded-3xl border-2 border-dashed border-[var(--ui-focus)] bg-[var(--ui-panel)]/95"
          aria-hidden
        >
          <span className="inline-flex items-center gap-2 text-sm font-medium text-[var(--phosphor-bright)]">
            <Paperclip className="h-4 w-4" aria-hidden />
            Drop .txt, .md, or .pdf files
          </span>
        </div>
      )}
      {children}
    </div>
  );
}
