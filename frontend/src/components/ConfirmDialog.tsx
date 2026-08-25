import { useId, useRef, type ReactNode } from 'react';
import { useFocusTrap } from '../utils/focusTrap';

export interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: 'default' | 'danger';
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  tone = 'default',
  loading = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const titleId = useId();
  const descriptionId = useId();
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const confirmRef = useRef<HTMLButtonElement | null>(null);

  useFocusTrap({
    open,
    containerRef: dialogRef,
    onEscape: onCancel,
    initialFocusRef: confirmRef,
  });

  if (!open) {
    return null;
  }

  return (
    <div
      className="settings-backdrop fixed inset-0 z-[60] flex items-end justify-center p-3 sm:items-center sm:p-6"
      onClick={onCancel}
    >
      <div
        ref={dialogRef}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        className="confirm-dialog settings-dialog w-full max-w-md p-6"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="type-eyebrow mb-1.5">Confirm</div>
        <h2
          id={titleId}
          className="font-display text-lg font-bold tracking-tight text-[var(--phosphor-bright)]"
        >
          {title}
        </h2>
        <p id={descriptionId} className="mt-2 text-[13.5px] leading-[1.55] text-[var(--ui-text-secondary)]">
          {message}
        </p>
        <div className="confirm-dialog__actions mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onCancel}
            disabled={loading}
            className="confirm-dialog__btn confirm-dialog__btn--ghost"
          >
            {cancelLabel}
          </button>
          <button
            ref={confirmRef}
            type="button"
            onClick={onConfirm}
            disabled={loading}
            data-tone={tone}
            className="confirm-dialog__btn"
          >
            {loading ? 'Working…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
