import { useEffect, useMemo, useRef, useState } from 'react';
import {
  sendMessage,
  switchPersona,
  uploadDocuments,
} from './api';
import { ChatHeader } from './components/ChatHeader';
import { ChatInput } from './components/ChatInput';
import { ChatMessageBubble } from './components/ChatMessageBubble';
import { Sidebar } from './components/Sidebar';
import { UploadStatusList } from './components/UploadStatusList';
import { useLocalStorage } from './hooks/useLocalStorage';
import { useTheme } from './hooks/useTheme';
import type { ChatMessage, ConversationMode, PersonaType, UploadStatus, WorkflowEventPayload } from './types';
import { playPrintTick } from './utils/terminalAudio';

interface ConversationSummary {
  id: string;
  title: string;
  updatedAt?: number;
  messageCount: number;
}

function createId() {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2);
}

const DEFAULT_MODEL_NAME = 'local-ollama';
const TERMINAL_NAME = 'MACHINE_ALPHA_7';

function sleep(ms: number) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

function formatTimestamp(timestamp: number) {
  return new Date(timestamp).toLocaleTimeString('en-US', { hour12: false });
}

function buildTerminalPrefix(role: 'user' | 'assistant', createdAt: number) {
  const node = role === 'user' ? 'USER1' : TERMINAL_NAME;
  return `[${formatTimestamp(createdAt)}] ${node}: > `;
}

function stripMachinePrefix(content: string) {
  return content.replace(/^\[\d{2}:\d{2}:\d{2}\]\s+MACHINE_ALPHA_7:\s*>\s*/i, '');
}

function deriveConversationTitle(history: ChatMessage[]): string {
  const firstUser = history.find((item) => item.role === 'user' && item.content.trim().length > 0);
  if (!firstUser) {
    return 'New conversation';
  }
  const compact = firstUser.content.replace(/\s+/g, ' ').trim();
  return compact.length > 32 ? `${compact.slice(0, 32)}...` : compact;
}

export default function App() {
  const [theme, setTheme] = useTheme();
  const [mode, setMode] = useLocalStorage<ConversationMode>('personal-ai-mode', 'smart');
  const [persona, setPersona] = useLocalStorage<PersonaType>('personal-ai-persona', 'ideal_chatbot');
  const [uiMode, setUiMode] = useLocalStorage<'classic' | 'terminal'>('personal-ai-ui-mode', 'classic');
  const [phosphor, setPhosphor] = useLocalStorage<'green' | 'amber'>('personal-ai-phosphor', 'green');
  const [sidebarCollapsed, setSidebarCollapsed] = useLocalStorage<boolean>('personal-ai-sidebar-collapsed', false);
  const [messages, setMessages] = useLocalStorage<ChatMessage[]>('personal-ai-history', []);
  const [conversationId, setConversationId] = useLocalStorage<string>('personal-ai-conversation-id', createId());
  const [conversationHistories, setConversationHistories] = useLocalStorage<Record<string, ChatMessage[]>>('personal-ai-conversations', {});
  const [uploadStatuses, setUploadStatuses] = useState<UploadStatus[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [latency, setLatency] = useState<number | undefined>(undefined);
  const controllerRef = useRef<AbortController | null>(null);
  const classicLogRef = useRef<HTMLDivElement | null>(null);
  const terminalLogRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const hasMountedRef = useRef(false);
  const isTerminalUI = uiMode === 'terminal';

  useEffect(() => {
    if (!hasMountedRef.current) {
      hasMountedRef.current = true;
      return;
    }

    const activeLog = isTerminalUI ? terminalLogRef.current : classicLogRef.current;
    activeLog?.scrollTo({
      top: activeLog.scrollHeight,
      behavior: 'auto',
    });
  }, [messages, isTerminalUI]);

  useEffect(() => {
    document.documentElement.setAttribute('data-phosphor', phosphor);
  }, [phosphor]);

  useEffect(() => {
    if (mode !== 'chat' && mode !== 'smart') {
      setMode('smart');
    }
  }, [mode, setMode]);

  useEffect(() => {
    if (uiMode === 'terminal' && mode !== 'chat') {
      setMode('chat');
    }
  }, [uiMode, mode, setMode]);

  useEffect(() => {
    if (uiMode === 'terminal' && sidebarCollapsed) {
      setSidebarCollapsed(false);
    }
  }, [uiMode, sidebarCollapsed, setSidebarCollapsed]);

  useEffect(() => {
    setConversationHistories((prev) => ({
      ...prev,
      [conversationId]: messages,
    }));
  }, [conversationId, messages, setConversationHistories]);

  const handleSend = async (text: string) => {
    if (!text.trim()) {
      return;
    }

    controllerRef.current?.abort();

    const userMessage: ChatMessage = {
      id: createId(),
      role: 'user',
      content: text,
      createdAt: Date.now(),
    };

    const assistantMessage: ChatMessage = {
      id: createId(),
      role: 'assistant',
      content: '',
      createdAt: Date.now(),
    };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setIsLoading(true);

    const terminalExperience = uiMode === 'terminal';

    const controller = new AbortController();
    controllerRef.current = controller;
    const startedAt = performance.now();
    const requestHistory = [...messages];

    try {
      const response = await sendMessage(mode, text, requestHistory, conversationId, controller.signal, (event: WorkflowEventPayload) => {
        if (event.type === 'workflow' && event.workflow) {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessage.id
                ? {
                    ...msg,
                    content: msg.content || 'Coordinating workflow...',
                    workflow: event.workflow,
                  }
                : msg,
            ),
          );
          return;
        }

        if (event.type === 'memory' && event.summary && event.phase) {
          const phase = event.phase;
          const summary = event.summary;
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessage.id
                ? {
                    ...msg,
                    content: msg.content || 'Coordinating workflow...',
                    workflowMemoryEvents: [
                      ...(msg.workflowMemoryEvents ?? []),
                      {
                        phase,
                        summary,
                      },
                    ],
                  }
                : msg,
            ),
          );
          return;
        }

        if (event.type === 'sources' && event.step_id && event.agent && event.sources) {
          const stepId = event.step_id;
          const agent = event.agent;
          const sourceCount = event.sources.length;
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessage.id
                ? {
                    ...msg,
                    content: msg.content || 'Coordinating workflow...',
                    workflowSourceEvents: [
                      ...(msg.workflowSourceEvents ?? []),
                      {
                        stepId,
                        agent,
                        count: sourceCount,
                      },
                    ],
                  }
                : msg,
            ),
          );
        }
      });

      const elapsed = performance.now() - startedAt;
      setLatency(elapsed);

      const finalMessage = response.message;

      if (terminalExperience) {
        const artificialDelay = 1000 + Math.floor(Math.random() * 2000);
        await sleep(artificialDelay);

        let typed = '';
        for (const char of finalMessage) {
          typed += char;
          if (char.trim()) {
            playPrintTick();
          }
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessage.id
                ? {
                    ...msg,
                    content: typed,
                    latencyMs: elapsed,
                    sources: response.sources,
                    workflow: response.workflow,
                  }
                : msg,
            ),
          );
          await sleep(char === '\n' ? 20 : 10);
        }
      } else {
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessage.id
              ? {
                  ...msg,
                  content: finalMessage,
                  latencyMs: elapsed,
                  sources: response.sources,
                  workflow: response.workflow,
                }
              : msg,
          ),
        );
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessage.id
            ? {
                ...msg,
                content: `⚠️ Unable to retrieve response. ${message}`,
              }
            : msg,
        ),
      );
    } finally {
      setIsLoading(false);
      controllerRef.current = null;
    }
  };

  const handleNewChat = () => {
    controllerRef.current?.abort();
    const newId = createId();
    setMessages([]);
    setConversationId(newId);
    setConversationHistories((prev) => ({
      ...prev,
      [newId]: [],
    }));
    setLatency(undefined);
  };

  const handleSelectConversation = (id: string) => {
    controllerRef.current?.abort();
    setConversationId(id);
    setMessages(conversationHistories[id] ?? []);
    setLatency(undefined);
  };

  const handleUpload = () => {
    fileInputRef.current?.click();
  };

  const handlePersonaChange = async (newPersona: PersonaType) => {
    try {
      await switchPersona(newPersona);
      setPersona(newPersona);
    } catch (error) {
      console.error('Failed to switch persona:', error);
    }
  };

  const onFilesSelected = async (files: FileList | null) => {
    if (!files?.length) {
      return;
    }

    const items: UploadStatus[] = Array.from(files).map((file) => ({
      id: createId(),
      name: file.name,
      status: 'uploading',
    }));
    setUploadStatuses((prev) => [...items, ...prev]);

    try {
      await uploadDocuments(Array.from(files));
      setUploadStatuses((prev) =>
        prev.map((item) =>
          items.some((it) => it.id === item.id)
            ? {
                ...item,
                status: 'success',
              }
            : item,
        ),
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Upload failed';
      setUploadStatuses((prev) =>
        prev.map((item) =>
          items.some((it) => it.id === item.id)
            ? {
                ...item,
                status: 'error',
                error: message,
              }
            : item,
        ),
      );
    } finally {
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const activeModel = useMemo(() => {
    if (mode === 'smart') {
      return 'smart router (smart_chat -> chat/rag/workflow)';
    }
    return 'chat (chat)';
  }, [mode]);

  const conversationSummaries = useMemo<ConversationSummary[]>(() => {
    const merged = {
      ...conversationHistories,
      [conversationId]: messages,
    };

    return Object.entries(merged)
      .map(([id, history]) => {
        const updatedAt = history[history.length - 1]?.createdAt;
        return {
          id,
          title: deriveConversationTitle(history),
          updatedAt,
          messageCount: history.length,
        };
      })
      .sort((a, b) => (b.updatedAt ?? 0) - (a.updatedAt ?? 0));
  }, [conversationHistories, conversationId, messages]);

  const activeConversationTitle = useMemo(() => deriveConversationTitle(messages), [messages]);

  const suggestionChips = useMemo(() => {
    return mode === 'smart'
      ? ['What should I pack for Kansas in April?', 'Summarize my notes with sources', 'Create a travel checklist and timeline']
      : ['Draft a concise email', 'Rewrite this in a friendly tone', 'Turn this into bullet points'];
  }, [mode]);

  const handleShareConversation = async () => {
    const payload = messages
      .map((entry) => `${entry.role.toUpperCase()}: ${entry.content}`)
      .join('\n\n');
    if (!payload) {
      return;
    }
    try {
      await navigator.clipboard.writeText(payload);
    } catch {
      console.warn('Clipboard unavailable for share action.');
    }
  };

  const handleCopyMessage = async (message: ChatMessage) => {
    try {
      await navigator.clipboard.writeText(message.content);
    } catch {
      console.warn('Clipboard unavailable for copy action.');
    }
  };

  const handleRegenerate = (assistantMessage: ChatMessage) => {
    const assistantIndex = messages.findIndex((item) => item.id === assistantMessage.id);
    if (assistantIndex <= 0) {
      return;
    }
    for (let i = assistantIndex - 1; i >= 0; i -= 1) {
      if (messages[i].role === 'user') {
        void handleSend(messages[i].content);
        return;
      }
    }
  };

  const handleFeedback = () => {
    // Placeholder for future backend feedback endpoint.
  };

  return (
    <div className={`app-shell ${isTerminalUI ? 'terminal-font' : 'classic-font'} flex min-h-0 flex-col overflow-hidden bg-[var(--ui-bg)] text-[var(--phosphor)] md:flex-row`}>
      <a href="#chat-main" className="skip-link">Skip to chat content</a>
      <Sidebar
        mode={mode}
        onModeChange={(value) => setMode(isTerminalUI ? 'chat' : value)}
        onNewChat={handleNewChat}
        onUpload={handleUpload}
        theme={theme}
        onSetTheme={setTheme}
        onSetUiMode={(targetMode) => setUiMode(targetMode)}
        phosphor={phosphor}
        onSetPhosphor={setPhosphor}
        persona={persona}
        onPersonaChange={handlePersonaChange}
        conversations={conversationSummaries}
        activeConversationId={conversationId}
        onSelectConversation={handleSelectConversation}
        uiMode={uiMode}
        sidebarCollapsed={sidebarCollapsed}
        onToggleSidebarCollapsed={() => setSidebarCollapsed((prev) => !prev)}
        settingsOpen={settingsOpen}
        onOpenSettings={() => setSettingsOpen(true)}
        onCloseSettings={() => setSettingsOpen(false)}
      />
      <main id="chat-main" aria-busy={isLoading} className={`${isTerminalUI ? '' : 'classic-atmosphere'} flex min-h-0 flex-1 flex-col border-t border-[var(--ui-border-strong)] bg-[var(--ui-panel-strong)] md:h-full md:border-t-0`}>
        <ChatHeader
          mode={mode}
          model={activeModel || DEFAULT_MODEL_NAME}
          latency={latency}
          isLoading={isLoading}
          uiMode={uiMode}
          conversationTitle={activeConversationTitle}
          onShareConversation={handleShareConversation}
          onNewChat={handleNewChat}
          onOpenSettings={() => setSettingsOpen(true)}
        />
        {isTerminalUI ? (
          <div className="flex h-full flex-1 flex-col bg-[var(--ui-bg)] p-2 md:p-3">
            <div className="crt-screen phosphor-text terminal-font flex h-full min-h-[28rem] min-w-0 flex-col rounded-md text-xl leading-6 sm:text-2xl sm:leading-7">
              <div ref={terminalLogRef} role="log" aria-live="polite" aria-relevant="additions text" className="flex-1 overflow-y-auto px-4 py-4 sm:px-5 sm:py-5">
                {messages.length === 0 ? (
                  <div className="mx-auto flex h-full w-full max-w-4xl items-center justify-center">
                    <div className="w-full max-w-2xl rounded-md border border-[var(--ui-border)] bg-[rgba(7,20,7,0.72)] px-5 py-6 text-center shadow-[0_0_0_1px_rgba(32,72,32,0.3)] sm:px-8 sm:py-8">
                      <div className="text-[11px] uppercase tracking-[0.45em] text-[var(--phosphor-dim)] sm:text-xs">
                        Terminal Session Ready
                      </div>
                      <div className="mt-3 text-3xl leading-none text-[var(--phosphor-bright)] sm:text-5xl">
                        {mode === 'smart' ? 'SMART MODE ONLINE' : 'QUICK MODE ONLINE'}
                      </div>
                      <div className="mt-4 text-base leading-6 text-[var(--phosphor)] sm:text-xl sm:leading-7">
                        {mode === 'smart'
                          ? 'Smart routing chooses direct chat, grounded retrieval, or full multi-agent workflow based on your prompt.'
                          : 'Quick mode runs low-latency direct chat for everyday prompts and fast iteration.'}
                      </div>
                      <div className="mt-5 grid gap-2 text-left text-sm text-[var(--phosphor-dim)] sm:grid-cols-2 sm:text-base">
                        <div className="rounded border border-[var(--ui-border)] bg-[rgba(6,14,6,0.55)] px-3 py-2">
                          &gt; {mode === 'smart' ? 'Complex prompts trigger planning, retrieval, synthesis, and review' : 'Use this for short asks, drafts, rewrites, and brainstorming'}
                        </div>
                        <div className="rounded border border-[var(--ui-border)] bg-[rgba(6,14,6,0.55)] px-3 py-2">
                          &gt; {mode === 'smart' ? 'Smart mode blends local docs + fresh web context when needed' : 'Switch to Smart mode when answers need grounding or multi-step reasoning'}
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-1">
                    {messages.map((message, index) => {
                      const isLast = index === messages.length - 1;
                      const isAssistantLoading = isLast && message.role === 'assistant' && isLoading && !message.content;
                      const displayContent =
                        message.role === 'assistant' ? stripMachinePrefix(message.content) : message.content;
                      return (
                        <div key={message.id} className="whitespace-pre-wrap break-words">
                          <span className="text-[var(--phosphor-bright)]">{buildTerminalPrefix(message.role === 'user' ? 'user' : 'assistant', message.createdAt)}</span>
                          <span>{isAssistantLoading ? 'PROCESSING REQUEST...' : displayContent}</span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              <div className="border-t border-[var(--ui-border)] px-4 py-3 sm:px-5">
                <ChatInput onSend={handleSend} disabled={isLoading} terminalMode />
              </div>
            </div>
          </div>
        ) : (
          <>
            <div ref={classicLogRef} role="log" aria-live="polite" aria-relevant="additions text" className="flex-1 overflow-y-auto px-4 py-4 sm:px-5 md:px-6">
              <div className="mx-auto flex w-full max-w-[76rem] flex-col gap-3">
                {messages.length === 0 && (
                  <div className="elevated-panel rounded-2xl p-5 text-left sm:p-6">
                    <div className="text-[11px] uppercase tracking-[0.35em] text-[var(--phosphor-dim)]">System Ready</div>
                    <div className="mt-3 text-2xl font-semibold text-[var(--phosphor-bright)] sm:text-3xl">
                      {mode === 'smart' ? 'Start a smart-routed conversation' : 'Start a direct model conversation'}
                    </div>
                    <div className="mt-3 max-w-2xl text-sm leading-6 text-[var(--phosphor)] sm:text-base">
                      {mode === 'smart'
                        ? 'Enter a prompt below and Smart mode will choose the right path: quick chat, grounded retrieval, or full workflow orchestration.'
                        : 'Enter a prompt below for fast direct responses. Use Smart mode when you need grounding, deeper analysis, or workflow trace.'}
                    </div>
                    <div className="mt-5 grid gap-3 text-sm text-[var(--phosphor-dim)] sm:grid-cols-2">
                      <div className="rounded-xl border border-[var(--ui-border)] bg-[color-mix(in_srgb,var(--ui-panel),transparent_18%)] px-3 py-3">
                        {mode === 'smart'
                          ? 'Smart mode can pull from internal docs and fresh public context.'
                          : 'Great for quick prompts, edits, and low-latency back-and-forth.'}
                      </div>
                      <div className="rounded-xl border border-[var(--ui-border)] bg-[color-mix(in_srgb,var(--ui-panel),transparent_18%)] px-3 py-3">
                        {mode === 'smart'
                          ? 'When needed, Smart mode returns workflow trace and step updates.'
                          : 'Use Smart mode for sources, retrieval, and multi-agent orchestration.'}
                      </div>
                    </div>
                  </div>
                )}
                {messages.map((message, index) => (
                  <ChatMessageBubble
                    key={message.id}
                    message={message}
                    isStreaming={isLoading && index === messages.length - 1}
                    onCopy={handleCopyMessage}
                    onRegenerate={handleRegenerate}
                    onFeedback={handleFeedback}
                  />
                ))}
                <UploadStatusList items={uploadStatuses} />
              </div>
            </div>
            <div className="border-t border-[var(--ui-border-strong)] bg-[color-mix(in_srgb,var(--ui-panel),transparent_6%)] px-4 py-4 sm:px-5 md:px-6 md:py-5">
              <div className="mx-auto max-w-[76rem]">
                <ChatInput
                  onSend={handleSend}
                  disabled={isLoading}
                  onAttach={handleUpload}
                  suggestions={suggestionChips}
                />
              </div>
            </div>
          </>
        )}
        <div className="sr-only" aria-live="polite" aria-atomic="true">
          {isLoading ? 'Assistant is generating a response.' : 'Assistant response complete.'}
        </div>
      </main>
      <input
        ref={fileInputRef}
        type="file"
        accept=".txt,.md,.pdf"
        multiple
        className="hidden"
        onChange={(event) => onFilesSelected(event.target.files)}
      />
    </div>
  );
}
