import { useEffect, useMemo, useRef, useState } from 'react';
import { ExternalLink } from 'lucide-react';
import { fetchDemoConfig, sendDemoMessage, type DemoConfig } from './api';
import { ChatInput } from './components/ChatInput';
import { CuraiLogo } from './components/CuraiLogo';
import { resolveCuraiLogoState } from './components/curaiLogoState';
import { VirtualizedMessageList } from './components/VirtualizedMessageList';
import type { ChatMessage } from './types';

const DEMO_SESSION_KEY = 'curai-demo-session-id';

function createId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2);
}

function getDemoSessionId(): string {
  try {
    let id = localStorage.getItem(DEMO_SESSION_KEY);
    if (!id || id.length < 8) {
      id = createId();
      localStorage.setItem(DEMO_SESSION_KEY, id);
    }
    return id;
  } catch {
    return createId();
  }
}

function parseDemoError(error: unknown): string {
  if (!(error instanceof Error)) {
    return 'Something went wrong. Please try again.';
  }
  const raw = error.message.trim();
  if (!raw) {
    return 'Something went wrong. Please try again.';
  }
  try {
    const parsed = JSON.parse(raw) as { detail?: string | { message?: string } };
    if (typeof parsed.detail === 'string') {
      return parsed.detail;
    }
    if (parsed.detail && typeof parsed.detail === 'object' && parsed.detail.message) {
      return parsed.detail.message;
    }
  } catch {
    // keep raw text
  }
  return raw;
}

export function DemoApp() {
  const [config, setConfig] = useState<DemoConfig | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [questionsUsed, setQuestionsUsed] = useState(0);
  const [questionsRemaining, setQuestionsRemaining] = useState(5);
  const [limitReached, setLimitReached] = useState(false);
  const [fullAppUrl, setFullAppUrl] = useState<string | null>(null);
  const sessionIdRef = useRef(getDemoSessionId());
  const messageLogRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const demoConfig = await fetchDemoConfig();
        if (cancelled) {
          return;
        }
        setConfig(demoConfig);
        setQuestionsRemaining(demoConfig.max_questions);
        setMessages([
          {
            id: createId(),
            role: 'assistant',
            content: demoConfig.intro,
            createdAt: Date.now(),
          },
        ]);
      } catch (error) {
        if (!cancelled) {
          setConfigError(parseDemoError(error));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const logoState = useMemo(
    () =>
      resolveCuraiLogoState({
        isLoading,
        hasBootstrapError: Boolean(configError),
        messages,
      }),
    [isLoading, configError, messages],
  );

  const handleSend = async (text: string) => {
    if (!config || isLoading || limitReached) {
      return;
    }

    const userMessage: ChatMessage = {
      id: createId(),
      role: 'user',
      content: text,
      createdAt: Date.now(),
    };
    const assistantPlaceholder: ChatMessage = {
      id: createId(),
      role: 'assistant',
      content: '',
      createdAt: Date.now(),
    };

    const nextMessages = [...messages, userMessage, assistantPlaceholder];
    setMessages(nextMessages);
    setIsLoading(true);

    try {
      const response = await sendDemoMessage({
        session_id: sessionIdRef.current,
        message: text,
        messages: nextMessages
          .filter((item) => item.role === 'user' || item.role === 'assistant')
          .filter((item) => item.content.trim().length > 0)
          .map((item) => ({ role: item.role, content: item.content })),
      });

      setQuestionsUsed(response.questions_used);
      setQuestionsRemaining(response.questions_remaining);
      setLimitReached(response.limit_reached);
      if (response.full_app_url) {
        setFullAppUrl(response.full_app_url);
      }

      setMessages((current) =>
        current.map((item) =>
          item.id === assistantPlaceholder.id
            ? {
                ...item,
                content: response.message,
                latencyMs: response.latency_ms,
              }
            : item,
        ),
      );
    } catch (error) {
      const message = parseDemoError(error);
      const isLimit = message.toLowerCase().includes('limit reached');
      if (isLimit) {
        setLimitReached(true);
        setQuestionsRemaining(0);
      }
      setMessages((current) =>
        current.map((item) =>
          item.id === assistantPlaceholder.id
            ? {
                ...item,
                content: isLimit
                  ? `${message} Sign in for unlimited conversations.`
                  : `⚠️ ${message}`,
              }
            : item,
        ),
      );
    } finally {
      setIsLoading(false);
    }
  };

  if (configError) {
    return (
      <div className="flex min-h-[100dvh] items-center justify-center bg-[var(--ui-bg)] px-4 text-[var(--phosphor)]">
        <p className="max-w-md text-center text-sm">{configError}</p>
      </div>
    );
  }

  if (!config) {
    return (
      <div className="flex min-h-[100dvh] items-center justify-center bg-[var(--ui-bg)]">
        <CuraiLogo state="thinking" size={40} />
      </div>
    );
  }

  const inputDisabled = isLoading || limitReached;

  return (
    <div className="flex h-[100dvh] min-h-[480px] flex-col bg-[var(--ui-bg)] text-[var(--phosphor)]">
      <header className="flex shrink-0 items-center justify-between gap-3 border-b border-[var(--ui-border)] bg-[var(--ui-panel)] px-4 py-2.5">
        <div className="flex min-w-0 items-center gap-2">
          <CuraiLogo state={logoState} size={28} />
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-[var(--phosphor-bright)]">CurAI Demo</p>
            <p className="truncate text-xs text-[var(--phosphor-dim)]">Portfolio preview</p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className="rounded-full border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] px-2.5 py-1 text-xs tabular-nums">
            {limitReached ? '0 left' : `${questionsRemaining} left`}
          </span>
          {fullAppUrl && (
            <a
              href={fullAppUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 rounded-full border border-[var(--ui-border)] px-2.5 py-1 text-xs font-medium transition hover:bg-[var(--ui-bg-elevated)]"
            >
              Full app
              <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>
      </header>

      <main ref={messageLogRef} className="min-h-0 flex-1 overflow-y-auto px-3 py-3 sm:px-4">
        <VirtualizedMessageList
          scrollRef={messageLogRef}
          messages={messages}
          isLoading={isLoading}
          isNearBottom
          editingUserMessageId={null}
          onCopy={() => undefined}
          onEditResend={() => undefined}
          onEditCancel={() => undefined}
          onEditFromError={() => undefined}
          onRegenerate={() => undefined}
          onRetry={() => undefined}
          onFeedback={() => undefined}
        />
      </main>

      <footer className="shrink-0 border-t border-[var(--ui-border)] bg-[var(--ui-panel)] px-3 py-3 sm:px-4">
        {limitReached ? (
          <div className="mb-2 rounded-xl border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] px-3 py-2 text-center text-sm text-[var(--phosphor-dim)]">
            You&apos;ve used all {config.max_questions} demo questions.
            {fullAppUrl ? (
              <>
                {' '}
                <a href={fullAppUrl} target="_blank" rel="noreferrer" className="font-medium text-[var(--ui-focus)] underline">
                  Open the full app
                </a>{' '}
                to keep chatting.
              </>
            ) : (
              ' Sign in on the full app to keep chatting.'
            )}
          </div>
        ) : (
          <p className="mb-2 text-center text-xs text-[var(--phosphor-dim)]">
            {questionsUsed > 0
              ? `${questionsUsed} of ${config.max_questions} questions used`
              : `Up to ${config.max_questions} free questions — no sign-in required`}
          </p>
        )}
        <ChatInput disabled={inputDisabled} hideAttach hideVoice onSend={handleSend} />
      </footer>
    </div>
  );
}
