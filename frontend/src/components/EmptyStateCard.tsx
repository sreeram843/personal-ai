import { FileText, GitCompare, Mail, MapPin, Sparkles, Zap } from 'lucide-react';
import type { ConversationMode } from '../types';
import { CuraiLogo } from './CuraiLogo';

interface Props {
  mode: ConversationMode;
  onSelectPrompt: (prompt: string) => void;
}

const STARTER_CHIPS = [
  { label: 'Search my docs', prompt: 'Search my uploaded documents and answer:', icon: FileText },
  { label: 'Places near me', prompt: 'Find good restaurants near me', icon: MapPin },
  { label: 'Compare options', prompt: 'Compare two options and list pros and cons for each.', icon: GitCompare },
  { label: 'Morning briefing', prompt: 'Give me a morning briefing with weather, news, and anything urgent.', icon: Zap },
  { label: 'Draft an email', prompt: 'Draft a concise, professional email for the following situation:', icon: Mail },
  { label: 'Deep analysis', prompt: 'Analyze this topic in depth, citing sources where possible:', icon: Sparkles },
] as const;

const HINTS = [
  { label: 'Grounded answers', prompt: 'What do my documents say about our Q3 roadmap?' },
  { label: 'Live data', prompt: 'What is the weather in Austin today?' },
  { label: 'Workflow trace', prompt: 'Plan and execute a multi-step research workflow on:' },
  { label: 'Quick edits', prompt: 'Rewrite this paragraph to be clearer and more concise:' },
] as const;

export function EmptyStateCard({ mode, onSelectPrompt }: Props) {
  const isSmart = mode === 'smart';

  return (
    <div className="empty-state-card elevated-panel rounded-xl p-4 text-left sm:p-5">
      <div className="empty-state-card__glow" aria-hidden />
      <div className="relative z-[1]">
        <div className="flex items-center gap-3">
          <div className="empty-state-icon grid h-11 w-11 shrink-0 place-content-center rounded-xl bg-[var(--ui-bg-elevated)] ring-1 ring-[var(--ui-border)]">
            <CuraiLogo state="idle" size={32} />
          </div>
          <div>
            <div className="type-eyebrow">New conversation</div>
            <div className="font-display mt-1 text-xl font-semibold leading-snug tracking-tight text-[var(--phosphor-bright)] sm:text-2xl">
              {isSmart ? 'Start a smart-routed conversation' : 'Start a direct model conversation'}
            </div>
          </div>
        </div>
        <div className="mt-2 text-base leading-relaxed text-[var(--phosphor)]">
          {isSmart
            ? 'Pick a starter below or type your own prompt. Smart mode routes to live data, your documents, or a multi-step workflow automatically.'
            : 'Pick a starter below or type your own prompt. Chat mode keeps responses fast and direct—switch to Smart for grounding and workflow trace.'}
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {STARTER_CHIPS.map(({ label, prompt, icon: Icon }) => (
            <button
              key={label}
              type="button"
              onClick={() => onSelectPrompt(prompt)}
              className="starter-chip inline-flex items-center gap-1.5 rounded-full border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] px-3 py-1.5 text-sm text-[var(--phosphor)] transition hover:border-[var(--ui-accent)] hover:text-[var(--phosphor-bright)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ui-accent)]"
            >
              <Icon className="h-3.5 w-3.5 shrink-0 text-[var(--ui-accent)]" aria-hidden />
              {label}
            </button>
          ))}
        </div>

        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {HINTS.map(({ label, prompt }) => (
            <button
              key={label}
              type="button"
              onClick={() => onSelectPrompt(prompt)}
              className="starter-hint rounded-lg border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] px-3 py-2.5 text-left text-sm leading-relaxed text-[var(--phosphor-dim)] transition hover:border-[var(--ui-accent)] hover:text-[var(--phosphor)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ui-accent)]"
            >
              <span className="type-eyebrow mb-0.5 block !text-[var(--ui-accent)] !tracking-[0.16em]">
                {label}
              </span>
              {prompt}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
