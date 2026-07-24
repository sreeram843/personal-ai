import { ChevronDown } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import type { ChatMessage } from '../types';

interface Props {
  message: ChatMessage;
  isStreaming?: boolean;
}

function statusLabel(status: string): string {
  return status.replace(/_/g, ' ');
}

export function ReasoningPanel({ message, isStreaming = false }: Props) {
  const hasWorkflow = Boolean(message.workflow?.steps?.length);
  const hasReasoning = Boolean(message.reasoning?.trim());
  const hasActiveWorkflow = useMemo(
    () =>
      Boolean(
        message.workflow?.steps.some(
          (step) => step.status === 'in_progress' || step.status === 'planned',
        ),
      ),
    [message.workflow?.steps],
  );
  const [open, setOpen] = useState(hasActiveWorkflow || isStreaming);

  useEffect(() => {
    if (hasActiveWorkflow || isStreaming) {
      setOpen(true);
    }
  }, [hasActiveWorkflow, isStreaming]);

  if (!hasWorkflow && !hasReasoning) {
    return null;
  }

  const activeStep = message.workflow?.steps.find((step) => step.status === 'in_progress');

  return (
    <details
      open={open}
      onToggle={(event) => setOpen((event.target as HTMLDetailsElement).open)}
      className="mt-2 w-full overflow-hidden rounded-[10px] border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] text-sm text-[var(--phosphor-dim)]"
    >
      <summary className="flex cursor-pointer list-none items-center gap-2 px-3.5 py-2.5 text-[13px] text-[var(--text-primary)] marker:content-none">
        <ChevronDown
          className={`h-3.5 w-3.5 shrink-0 text-[var(--phosphor-dim)] transition-transform ${open ? 'rotate-180' : '-rotate-90'}`}
          aria-hidden
        />
        <span>{isStreaming ? 'Working…' : 'Reasoning & workflow trace'}</span>
        {message.sentiment && message.sentiment !== 'neutral' && (
          <span className="rounded-full bg-[var(--ui-bg)] px-2 py-0.5 text-xs capitalize text-[var(--phosphor-dim)]">
            tone: {message.sentiment}
          </span>
        )}
      </summary>

      <div className="flex flex-col gap-2.5 border-t border-[var(--ui-border)] px-3.5 py-3">
        {isStreaming && activeStep && (
          <p className="text-xs leading-relaxed text-[var(--phosphor-dim)]">
            {activeStep.title}
            {activeStep.summary ? ` — ${activeStep.summary}` : ''}
          </p>
        )}

        {hasWorkflow && message.workflow && (
          <section>
            <h4 className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--phosphor-dim)]">
              Workflow steps
            </h4>
            <ol className="space-y-1.5">
              {message.workflow.steps.map((step) => (
                <li key={step.id} className="rounded-lg bg-[var(--ui-bg)] px-2.5 py-2 text-[13px] text-[var(--text-primary)]">
                  <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                    <span className="font-medium">{step.title}</span>
                    <span className="text-[11.5px] capitalize text-[var(--phosphor-dim)]">
                      {step.agent} · {statusLabel(step.status)}
                    </span>
                  </div>
                  {step.summary && <p className="mt-0.5 text-xs leading-relaxed text-[var(--phosphor-dim)]">{step.summary}</p>}
                </li>
              ))}
            </ol>
          </section>
        )}

        {hasReasoning && (
          <section>
            <h4 className="mb-1.5 mt-1 text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--phosphor-dim)]">
              Model reasoning
            </h4>
            <pre className="whitespace-pre-wrap break-words font-sans text-[12.5px] leading-[1.6] text-[var(--ui-text-secondary)]">
              {message.reasoning}
            </pre>
          </section>
        )}
      </div>
    </details>
  );
}
