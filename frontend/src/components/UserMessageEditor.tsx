import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent } from 'react';
import { clsx } from 'clsx';
import { Check, X } from 'lucide-react';

interface Props {
  initialContent: string;
  disabled?: boolean;
  onSubmit: (content: string) => void;
  onCancel: () => void;
}

const MIN_TA = 44;

export function UserMessageEditor({ initialContent, disabled, onSubmit, onCancel }: Props) {
  const [value, setValue] = useState(initialContent);
  const [needsScroll, setNeedsScroll] = useState(false);
  const textRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    textRef.current?.focus();
    textRef.current?.select();
  }, []);

  useLayoutEffect(() => {
    const el = textRef.current;
    if (!el) {
      return;
    }
    el.style.height = '0px';
    const h = Math.max(MIN_TA, el.scrollHeight);
    el.style.height = `${h}px`;
    // Only enable the scrollbar once content genuinely exceeds the CSS
    // max-height cap, so the box never shows one while short or empty.
    setNeedsScroll(el.scrollHeight > el.clientHeight);
  }, [value]);

  const handleSubmit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) {
      return;
    }
    onSubmit(trimmed);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      onCancel();
      return;
    }
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="flex w-full flex-col gap-2">
      <textarea
        ref={textRef}
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        rows={1}
        className={clsx(
          'min-h-[44px] w-full max-h-[45vh] resize-none rounded-xl border border-[var(--ui-border-strong)] bg-[var(--ui-bg)] px-3 py-2 text-base leading-normal text-[var(--phosphor)] outline-none ring-[var(--ui-focus)] focus-visible:ring-2',
          needsScroll ? 'overflow-y-auto' : 'overflow-y-hidden',
        )}
        aria-label="Edit message"
      />
      <div className="flex items-center justify-end gap-1">
        <button
          type="button"
          onClick={onCancel}
          disabled={disabled}
          className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-medium text-[var(--phosphor-dim)] transition hover:bg-[var(--ui-bg-elevated)] hover:text-[var(--phosphor)]"
        >
          <X className="h-3.5 w-3.5" aria-hidden />
          Cancel
        </button>
        <button
          type="button"
          onClick={handleSubmit}
          disabled={disabled || !value.trim()}
          className="inline-flex items-center gap-1 rounded-lg bg-[var(--ui-focus)] px-2.5 py-1.5 text-xs font-medium text-[var(--ui-accent-fg)] transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Check className="h-3.5 w-3.5" aria-hidden />
          Send
        </button>
      </div>
    </div>
  );
}
