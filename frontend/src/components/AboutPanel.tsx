import { X } from 'lucide-react';
import { CuraiLogo } from './CuraiLogo';

interface Props {
  open: boolean;
  onClose: () => void;
}

export function AboutPanel({ open, onClose }: Props) {
  if (!open) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-end bg-black/30 p-3 backdrop-blur-[2px]"
      role="dialog"
      aria-modal="true"
      aria-label="About CurAI"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-xl border border-[var(--ui-border-strong)] bg-[var(--ui-panel-strong)] p-4 shadow-xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <CuraiLogo state="idle" size={36} />
            <div>
              <div className="text-xs uppercase tracking-[0.28em] text-[var(--phosphor-dim)]">About</div>
              <div className="text-lg font-semibold text-[var(--phosphor-bright)]">CurAI</div>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="grid h-8 w-8 shrink-0 place-content-center rounded border border-[var(--ui-border)] transition hover:bg-[var(--ui-bg-elevated)]"
            aria-label="Close about panel"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-4 text-sm leading-relaxed text-[var(--phosphor)]">
          <p>
            CurAI is a private assistant workspace for grounded chat, document retrieval, and smart multi-step
            workflows — inspired by the spirit of discovery. Everything is scoped to your account.
          </p>

          <div>
            <div className="mb-1 text-[10px] uppercase tracking-[0.18em] text-[var(--phosphor-dim)]">What you can do</div>
            <ul className="list-disc space-y-1 pl-5 text-[var(--phosphor)]">
              <li>Chat in Direct mode for fast responses</li>
              <li>Use Smart mode for retrieval, live data, and orchestrated workflows</li>
              <li>Upload documents to build a personal knowledge base</li>
              <li>Keep a private history of conversations on this device and server</li>
            </ul>
          </div>

          <div>
            <div className="mb-1 text-[10px] uppercase tracking-[0.18em] text-[var(--phosphor-dim)]">Privacy</div>
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
