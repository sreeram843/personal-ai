import { CheckCircle2, ChevronDown, CircleDashed, Loader2, MinusCircle, XCircle } from 'lucide-react';
import { useMemo, useState } from 'react';
import type { WorkflowStep, WorkflowTrace } from '../types';
import { parseReasoningSections } from '../utils/parseReasoningSections';

interface Props {
  reasoning?: string;
  workflow?: WorkflowTrace;
}

const STATUS_LABEL: Record<WorkflowStep['status'], string> = {
  planned: 'Planned',
  in_progress: 'In progress',
  completed: 'Complete',
  failed: 'Failed',
  skipped: 'Skipped',
};

const STATUS_ICON: Record<WorkflowStep['status'], typeof CheckCircle2> = {
  planned: CircleDashed,
  in_progress: Loader2,
  completed: CheckCircle2,
  failed: XCircle,
  skipped: MinusCircle,
};

const STATUS_COLOR: Record<WorkflowStep['status'], string> = {
  planned: 'text-[var(--phosphor-dim)]',
  in_progress: 'text-[var(--ui-accent)]',
  completed: 'text-[#6fcf97]',
  failed: 'text-[#f87171]',
  skipped: 'text-[var(--phosphor-dim)]',
};

const STAGE_ACCENT: Record<string, string> = {
  planner: 'border-[rgba(96,165,250,0.35)] bg-[rgba(96,165,250,0.12)] text-[#93c5fd]',
  synthesizer: 'border-[rgba(224,164,70,0.4)] bg-[rgba(224,164,70,0.12)] text-[#e0a446]',
  reviewer: 'border-[rgba(52,211,153,0.35)] bg-[rgba(52,211,153,0.12)] text-[#6ee7b7]',
  writer: 'border-[rgba(125,211,252,0.35)] bg-[rgba(125,211,252,0.12)] text-[#7dd3fc]',
};

function stepLine(step: WorkflowStep): string {
  return step.title || step.summary || step.id;
}

function stageBadgeClass(title: string): string {
  const key = title.trim().toLowerCase();
  return (
    STAGE_ACCENT[key] ??
    'border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] text-[var(--phosphor)]'
  );
}

/**
 * Collapsible "Reasoning & workflow trace" panel — mirrors the mockup in
 * CurieAI Designs/CurieAI Chat Content.dc.html: a workflow-steps list
 * (agent · status) plus the model's own reasoning text underneath.
 *
 * Sized and colored as secondary/debug content — smaller and dimmer than the
 * main answer text, so it reads as supplementary rather than competing for
 * attention.
 */
export function ReasoningPanel({ reasoning, workflow }: Props) {
  const [open, setOpen] = useState(false);
  const steps = workflow?.steps ?? [];
  const sections = useMemo(
    () => (reasoning ? parseReasoningSections(reasoning) : []),
    [reasoning],
  );
  const hasReasoning = sections.length > 0;
  if (!steps.length && !hasReasoning) {
    return null;
  }

  return (
    <details
      open={open}
      onToggle={(event) => setOpen((event.target as HTMLDetailsElement).open)}
      className="mt-2 w-full overflow-hidden rounded-[10px] border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)]"
    >
      <summary className="flex cursor-pointer list-none items-center gap-1.5 px-3 py-2 text-[12px] text-[var(--phosphor-dim)] marker:content-none">
        <ChevronDown
          className={`h-3 w-3 shrink-0 transition-transform ${open ? 'rotate-180' : '-rotate-90'}`}
          aria-hidden
        />
        <span className="font-medium text-[var(--phosphor)]">Reasoning &amp; workflow trace</span>
        {steps.length > 0 ? <span>· {steps.length} step{steps.length === 1 ? '' : 's'}</span> : null}
      </summary>
      <div className="space-y-3 border-t border-[var(--ui-border)] px-3 py-2.5">
        {steps.length > 0 ? (
          <div>
            <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.07em] text-[var(--phosphor-dim)]">
              Workflow steps
            </div>
            <ul className="space-y-1">
              {steps.map((step) => {
                const Icon = STATUS_ICON[step.status];
                return (
                  <li key={step.id} className="flex items-start gap-2 rounded-md bg-[var(--ui-bg)] px-2.5 py-1.5">
                    <Icon
                      className={`mt-[2px] h-3 w-3 shrink-0 ${STATUS_COLOR[step.status]} ${
                        step.status === 'in_progress' ? 'animate-spin' : ''
                      }`}
                      aria-hidden
                    />
                    <div className="min-w-0 flex-1 text-[12px] leading-snug">
                      <span className="text-[var(--phosphor)]">{stepLine(step)}</span>
                      <span className="ml-1.5 text-[10.5px] text-[var(--phosphor-dim)]">
                        {step.agent} · {STATUS_LABEL[step.status]}
                      </span>
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
        ) : null}
        {hasReasoning ? (
          <div>
            <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.07em] text-[var(--phosphor-dim)]">
              Model reasoning
            </div>
            <div className="max-h-56 space-y-2.5 overflow-y-auto rounded-lg bg-[var(--ui-bg)] px-2.5 py-2">
              {sections.map((section, index) => (
                <div key={`${section.title ?? 'note'}-${index}`} className="space-y-1.5">
                  {section.title ? (
                    <span
                      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.06em] ${stageBadgeClass(section.title)}`}
                    >
                      {section.title}
                    </span>
                  ) : null}
                  {section.body ? (
                    <p className="whitespace-pre-line text-[11.5px] leading-[1.6] text-[var(--phosphor-dim)]">
                      {section.body}
                    </p>
                  ) : null}
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </details>
  );
}
