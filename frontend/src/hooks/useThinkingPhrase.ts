import { useEffect, useMemo, useState } from 'react';
import type { ChatMessage } from '../types';

const DEFAULT_PHRASES = [
  'Thinking through the request and gathering context…',
  'Comparing options and drafting a clear answer…',
  'Checking details before responding…',
  'Almost there…',
] as const;

const WEB_PHRASES = [
  'Searching the web and reading sources…',
  'Cross-checking facts across results…',
  'Synthesizing findings into an answer…',
] as const;

const WORKFLOW_PHRASES = [
  'Planning workflow steps and agent handoffs…',
  'Running agents and correlating intermediate results…',
  'Reviewing outputs before the final answer…',
] as const;

function pickPhrasePool(message: ChatMessage): readonly string[] {
  if (message.showLiveSkeleton) {
    return ['Loading live data and verifying sources…', 'Fetching the latest figures…'] as const;
  }
  const steps = message.workflow?.steps ?? [];
  if (steps.some((step) => step.status === 'in_progress' || step.status === 'planned')) {
    return WORKFLOW_PHRASES;
  }
  if (
    steps.some((step) => /web|search|fetch|browse/i.test(`${step.title ?? ''} ${step.summary ?? ''}`))
  ) {
    return WEB_PHRASES;
  }
  return DEFAULT_PHRASES;
}

function activeWorkflowLabel(message: ChatMessage): string | null {
  const active = message.workflow?.steps.find((step) => step.status === 'in_progress');
  if (!active) {
    return null;
  }
  const title = active.title?.trim();
  const summary = active.summary?.trim();
  if (title && summary) {
    return `${title} — ${summary}`;
  }
  return title || summary || null;
}

export function useThinkingPhrase(message: ChatMessage, isStreaming: boolean): string {
  const phrases = useMemo(() => pickPhrasePool(message), [message]);
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (!isStreaming) {
      setIndex(0);
      return;
    }
    const intervalId = window.setInterval(() => {
      setIndex((current) => (current + 1) % phrases.length);
    }, 2800);
    return () => window.clearInterval(intervalId);
  }, [isStreaming, phrases]);

  const workflowLabel = activeWorkflowLabel(message);
  if (workflowLabel) {
    return workflowLabel;
  }

  return phrases[index] ?? DEFAULT_PHRASES[0];
}
