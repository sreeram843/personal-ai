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
      className="mt-2 w-full rounded-lg border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)]/60 text-sm text-[var(--phosphor-dim)]"
    >
      <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-2 text-[var(--phosphor)] marker:content-none">
        <ChevronDown
          className={`h-3.5 w-3.5 shrink-0 transition-transform ${open ? 'rotate-180' : ''}`}
          aria-hidden
        />
        <span>{isStreaming ? 'Working…' : 'Reasoning & workflow trace'}</span>
        {message.sentiment && message.sentiment !== 'neutral' && (
          <span className="rounded-full bg-[var(--ui-bg)] px-2 py-0.5 text-xs capitalize text-[var(--phosphor-dim)]">
            tone: {message.sentiment}
          </span>
        )}
      </summary>

      <div className="space-y-3 border-t border-[var(--ui-border)] px-3 py-2.5">
        {isStreaming && activeStep && (
          <p className="text-xs leading-relaxed text-[var(--phosphor-dim)]">
            {activeStep.title}
            {activeStep.summary ? ` — ${activeStep.summary}` : ''}
          </p>
        )}

        {hasWorkflow && message.workflow && (
          <section>
            <h4 className="mb-1.5 text-xs font-medium uppercase tracking-wide text-[var(--phosphor-dim)]">
              Workflow steps
            </h4>
            <ol className="space-y-1.5">
              {message.workflow.steps.map((step) => (
                <li key={step.id} className="rounded-md bg-[var(--ui-bg)]/50 px-2.5 py-1.5">
                  <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                    <span className="font-medium text-[var(--phosphor)]">{step.title}</span>
                    <span className="text-xs capitalize text-[var(--phosphor-dim)]">
                      {step.agent} · {statusLabel(step.status)}
                    </span>
                  </div>
                  {step.summary && <p className="mt-0.5 text-xs leading-relaxed">{step.summary}</p>}
                </li>
              ))}
            </ol>
          </section>
        )}

        {hasReasoning && (
          <section>
            <h4 className="mb-1.5 text-xs font-medium uppercase tracking-wide text-[var(--phosphor-dim)]">
              Model reasoning
            </h4>
            <pre className="whitespace-pre-wrap break-words font-sans text-xs leading-relaxed text-[var(--phosphor-dim)]">
              {message.reasoning}
            </pre>
          </section>
        )}
      </div>
    </details>
  );
}
