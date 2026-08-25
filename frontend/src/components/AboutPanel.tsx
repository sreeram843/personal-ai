import { useRef } from 'react';
import { X } from 'lucide-react';
import { useFocusTrap } from '../utils/focusTrap';
import { CuraiLogo } from './CuraiLogo';

interface Props {
  open: boolean;
  onClose: () => void;
}

export function AboutPanel({ open, onClose }: Props) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const closeRef = useRef<HTMLButtonElement | null>(null);

  useFocusTrap({
    open,
    containerRef: dialogRef,
    onEscape: onClose,
    initialFocusRef: closeRef,
  });

  if (!open) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/30 p-0 backdrop-blur-[2px] md:items-start md:justify-end md:p-3"
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        className="w-full max-h-[85dvh] overflow-y-auto rounded-t-2xl border border-[var(--ui-border-strong)] bg-[var(--ui-panel-strong)] p-4 shadow-xl md:max-h-none md:max-w-md md:rounded-xl"
        style={{ paddingBottom: 'max(1rem, var(--safe-area-bottom))' }}
        role="dialog"
        aria-modal="true"
        aria-label="About CurieAI"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <CuraiLogo state="idle" size={36} />
            <div>
              <div className="type-eyebrow !tracking-[0.28em]">About</div>
              <div className="font-display text-lg font-semibold tracking-tight text-[var(--phosphor-bright)]">CurieAI</div>
            </div>
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            className="touch-target grid h-10 w-10 shrink-0 place-content-center rounded border border-[var(--ui-border)] transition hover:bg-[var(--ui-bg-elevated)] md:h-8 md:w-8"
            aria-label="Close about panel"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-4 text-sm leading-relaxed text-[var(--phosphor)]">
          <p>
            CurieAI is a private assistant workspace for grounded chat, document retrieval, and smart multi-step
            workflows — inspired by Marie Curie's spirit of discovery. The name blends Curie and AI; the logo's
            orbiting electrons and glowing bulb echo scientific inquiry and the spark of insight. Everything is
            scoped to your account.
          </p>

          <div>
            <div className="mb-1 type-eyebrow !tracking-[0.18em]">What you can do</div>
            <ul className="list-disc space-y-1 pl-5 text-[var(--phosphor)]">
              <li>Chat with automatic routing to live data, your documents, or multi-step workflows</li>
              <li>Upload documents to build a personal knowledge base</li>
              <li>Keep a private history of conversations on this device and server</li>
            </ul>
          </div>

          <div>
            <div className="mb-1 type-eyebrow !tracking-[0.18em]">Privacy</div>
            <p>
              Conversations are stored per user. Only you can list, open, or delete your chats after signing in.
            </p>
          </div>

          <div className="rounded-lg border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] px-3 py-2.5 text-xs text-[var(--phosphor-dim)]">
            Built with FastAPI, React, Qdrant, and local or cloud LLM providers.
          </div>
        </div>
      </div>
    </div>
  );
}
