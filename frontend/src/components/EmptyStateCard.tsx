import { FileText, GitCompare, Mail, Sparkles, Zap } from 'lucide-react';
import type { ConversationMode } from '../types';
import { CuraiLogo } from './CuraiLogo';

interface Props {
  mode: ConversationMode;
  onSelectPrompt: (prompt: string) => void;
}

const CHAT_CHIPS = [
  { label: 'Summarize a document', prompt: 'Summarize the key points from a document I will paste below.', icon: FileText },
  { label: 'Compare two things', prompt: 'Compare two options and list pros and cons for each.', icon: GitCompare },
  { label: 'Draft an email', prompt: 'Draft a concise, professional email for the following situation:', icon: Mail },
] as const;

const SMART_CHIPS = [
  { label: 'Search my docs', prompt: 'Search my uploaded documents and answer:', icon: FileText },
  { label: 'Deep analysis', prompt: 'Analyze this topic in depth, citing sources where possible:', icon: Sparkles },
  { label: 'Morning briefing', prompt: 'Give me a morning briefing with weather, news, and anything urgent.', icon: Zap },
] as const;

export function EmptyStateCard({ mode, onSelectPrompt }: Props) {
  const chips = mode === 'smart' ? SMART_CHIPS : CHAT_CHIPS;
  const hints =
    mode === 'smart'
      ? [
          { label: 'Grounded answers', prompt: 'What do my documents say about our Q3 roadmap?' },
          { label: 'Workflow trace', prompt: 'Plan and execute a multi-step research workflow on:' },
        ]
      : [
          { label: 'Quick edits', prompt: 'Rewrite this paragraph to be clearer and more concise:' },
          { label: 'Fast back-and-forth', prompt: 'Help me brainstorm ideas for:' },
        ];

  return (
    <div className="empty-state-card mx-auto flex min-h-[58vh] max-w-[560px] flex-col items-center justify-center gap-5 px-4 text-center">
      <div className="empty-state-icon grid h-[60px] w-[60px] shrink-0 place-content-center rounded-2xl bg-[var(--ui-bg-elevated)]">
        <CuraiLogo state="idle" size={38} />
      </div>
      <div className="font-display text-[26px] font-semibold leading-snug tracking-tight text-[var(--phosphor-bright)]">
        {mode === 'smart' ? 'Start a smart-routed conversation' : 'Start a direct model conversation'}
      </div>
      <div className="max-w-[440px] text-[14.5px] leading-relaxed text-[var(--phosphor-dim)]">
        {mode === 'smart'
          ? 'Pick a starter below or type your own prompt. Smart mode routes to chat, retrieval, or workflow as needed.'
          : 'Pick a starter below or type your own prompt for fast, direct responses.'}
      </div>

      <div className="flex flex-wrap items-center justify-center gap-2.5">
        {chips.map(({ label, prompt, icon: Icon }) => (
          <button
            key={label}
            type="button"
            onClick={() => onSelectPrompt(prompt)}
            className="starter-chip inline-flex items-center gap-[7px] rounded-full border border-[var(--ui-chip-border)] px-4 py-[9px] text-[13px] text-[var(--ui-chip-text)] transition hover:border-[var(--ui-accent)] hover:text-[var(--phosphor-bright)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ui-accent)]"
          >
            <Icon className="h-[13px] w-[13px] shrink-0 text-[var(--ui-accent)]" aria-hidden />
            {label}
          </button>
        ))}
      </div>

      <div className="mt-1 grid w-full gap-2 sm:grid-cols-2">
        {hints.map(({ label, prompt }) => (
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
  );
}
