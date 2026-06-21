import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { AuthConfig, CurrentUser } from './api';
import { sendMessage, uploadDocuments } from './api';
import { AboutPanel } from './components/AboutPanel';
import { ChatHeader } from './components/ChatHeader';
import { ChatInput } from './components/ChatInput';
import { VirtualizedMessageList } from './components/VirtualizedMessageList';
import { SettingsPanel } from './components/SettingsPanel';
import { Sidebar } from './components/Sidebar';
import { UploadStatusList } from './components/UploadStatusList';
import { useLocalStorage } from './hooks/useLocalStorage';
import { useTheme } from './hooks/useTheme';
import {
  useCreateConversation,
  useDeleteConversation,
  useConversationMessages,
  useConversations,
  useInvalidateConversationData,
  useLogout,
  useUpdateConversation,
} from './query/hooks';
import {
  appendOptimisticSend,
  promoteDraftMessages,
  updateCachedMessage,
  writeCachedMessages,
} from './query/messageCache';
import type { ChatMessage, ConversationMode, UploadStatus, WorkflowEventPayload } from './types';

function createId() {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2);
}

function deriveConversationTitle(history: ChatMessage[]): string {
  const firstUser = history.find((item) => item.role === 'user' && item.content.trim().length > 0);
  if (!firstUser) {
    return 'New conversation';
  }
  const compact = firstUser.content.replace(/\s+/g, ' ').trim();
  return compact.length > 32 ? `${compact.slice(0, 32)}...` : compact;
}

function formatQueryError(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return fallback;
}

interface AppProps {
  authConfig: AuthConfig;
  user: CurrentUser;
}

export default function App({ user }: AppProps) {
  const queryClient = useQueryClient();
  const [theme, setTheme] = useTheme();
  const [mode, setMode] = useLocalStorage<ConversationMode>('personal-ai-mode', 'smart');
  const [sidebarCollapsed, setSidebarCollapsed] = useLocalStorage<boolean>('personal-ai-sidebar-collapsed', false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [uploadStatuses, setUploadStatuses] = useState<UploadStatus[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [aboutOpen, setAboutOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [latency, setLatency] = useState<number | undefined>(undefined);
  const controllerRef = useRef<AbortController | null>(null);
  const sendInFlightRef = useRef(false);
  const messageLogRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const authReady = true;
  const conversationsQuery = useConversations(authReady);
  const messagesQuery = useConversationMessages(conversationId, authReady);
  const createConversationMutation = useCreateConversation();
  const deleteConversationMutation = useDeleteConversation();
  const updateConversationMutation = useUpdateConversation();
  const logout = useLogout();
  const { invalidateAfterSend } = useInvalidateConversationData();

  const conversations = conversationsQuery.data ?? [];
  const messages = messagesQuery.data ?? [];

  const bootstrapError = useMemo(() => {
    if (conversationsQuery.isError) {
      return formatQueryError(conversationsQuery.error, 'Failed to load conversations');
    }
    if (messagesQuery.isError) {
      return formatQueryError(messagesQuery.error, 'Failed to load conversation messages');
    }
    return null;
  }, [conversationsQuery.isError, conversationsQuery.error, messagesQuery.isError, messagesQuery.error]);

  const isBootstrapping = authReady && conversationsQuery.isLoading && !conversationsQuery.data;

  const handleRetryBootstrap = () => {
    if (conversationsQuery.isError) {
      void conversationsQuery.refetch();
    }
    if (messagesQuery.isError) {
      void messagesQuery.refetch();
    }
  };

  useEffect(() => {
    document.documentElement.removeAttribute('data-phosphor');
  }, []);

  useEffect(() => {
    if (mode !== 'chat' && mode !== 'smart') {
      setMode('smart');
    }
  }, [mode, setMode]);

  const handleSend = async (
    text: string,
    options?: {
      /** Regenerate: keep existing user turn, replace assistant reply only. */
      regeneratePrefix?: ChatMessage[];
    },
  ) => {
    if (!text.trim() || isBootstrapping || sendInFlightRef.current) {
      return;
    }

    sendInFlightRef.current = true;
    controllerRef.current?.abort();

    const activeConversationId = conversationId;
    const isRegenerate = Boolean(options?.regeneratePrefix);
    const assistantMessage: ChatMessage = {
      id: createId(),
      role: 'assistant',
      content: '',
      createdAt: Date.now(),
    };

    let requestHistory: ChatMessage[];
    if (isRegenerate && options?.regeneratePrefix) {
      requestHistory = options.regeneratePrefix;
      writeCachedMessages(queryClient, activeConversationId, [...requestHistory, assistantMessage]);
    } else {
      const userMessage: ChatMessage = {
        id: createId(),
        role: 'user',
        content: text,
        createdAt: Date.now(),
      };
      requestHistory = appendOptimisticSend(
        queryClient,
        activeConversationId,
        userMessage,
        assistantMessage,
      );
    }
    setIsLoading(true);

    const controller = new AbortController();
    controllerRef.current = controller;
    const startedAt = performance.now();

    try {
      const response = await sendMessage(mode, text, requestHistory, activeConversationId, controller.signal, (event: WorkflowEventPayload) => {
        if (event.type === 'workflow' && event.workflow) {
          updateCachedMessage(queryClient, activeConversationId, assistantMessage.id, (msg) => ({
            ...msg,
            content: msg.content || 'Coordinating workflow...',
            workflow: event.workflow,
          }));
          return;
        }

        if (event.type === 'memory' && event.summary && event.phase) {
          const phase = event.phase;
          const summary = event.summary;
          updateCachedMessage(queryClient, activeConversationId, assistantMessage.id, (msg) => ({
            ...msg,
            content: msg.content || 'Coordinating workflow...',
            workflowMemoryEvents: [
              ...(msg.workflowMemoryEvents ?? []),
              {
                phase,
                summary,
              },
            ],
          }));
          return;
        }

        if (event.type === 'sources' && event.step_id && event.agent && event.sources) {
          const stepId = event.step_id;
          const agent = event.agent;
          const sourceCount = event.sources.length;
          updateCachedMessage(queryClient, activeConversationId, assistantMessage.id, (msg) => ({
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
          }));
        }
      });

      const elapsed = performance.now() - startedAt;
      setLatency(elapsed);

      const finalMessage = response.message;
      let nextConversationId = response.conversation_id ?? activeConversationId;

      if (response.conversation_id && !activeConversationId) {
        promoteDraftMessages(queryClient, response.conversation_id);
        nextConversationId = response.conversation_id;
        setConversationId(response.conversation_id);
      }

      updateCachedMessage(queryClient, nextConversationId, assistantMessage.id, (msg) => ({
        ...msg,
        content: finalMessage,
        latencyMs: elapsed,
        sources: response.sources,
        workflow: response.workflow,
      }));

      invalidateAfterSend(nextConversationId);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      writeCachedMessages(queryClient, activeConversationId, [
        ...requestHistory,
        {
          ...assistantMessage,
          content: `⚠️ Unable to retrieve response. ${message}`,
        },
      ]);
    } finally {
      setIsLoading(false);
      sendInFlightRef.current = false;
      controllerRef.current = null;
    }
  };

  const handleNewChat = async () => {
    controllerRef.current?.abort();
    setLatency(undefined);
    writeCachedMessages(queryClient, null, []);

    try {
      const created = await createConversationMutation.mutateAsync(mode);
      setConversationId(created.id);
      writeCachedMessages(queryClient, created.id, []);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to start a new conversation';
      writeCachedMessages(queryClient, null, [
        {
          id: createId(),
          role: 'assistant',
          content: `⚠️ Unable to start a new conversation. ${message}`,
          createdAt: Date.now(),
        },
      ]);
    }
  };

  const handleSelectConversation = (id: string) => {
    controllerRef.current?.abort();
    setConversationId(id);
    setLatency(undefined);
  };

  const activeConversationTitle = useMemo(() => {
    const active = conversations.find((item) => item.id === conversationId);
    if (active?.title && active.title !== 'New conversation') {
      return active.title;
    }
    return deriveConversationTitle(messages);
  }, [conversationId, conversations, messages]);

  const showToast = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(null), 2200);
  };

  const handleDeleteConversation = async (id: string) => {
    try {
      await deleteConversationMutation.mutateAsync(id);
      if (conversationId === id) {
        controllerRef.current?.abort();
        setConversationId(null);
        setLatency(undefined);
        writeCachedMessages(queryClient, null, []);
      }
      showToast('Conversation deleted.');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to delete conversation';
      showToast(message);
    }
  };

  const handleRenameConversation = async (id: string, title: string) => {
    try {
      await updateConversationMutation.mutateAsync({ conversationId: id, title });
      showToast('Conversation renamed.');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to rename conversation';
      showToast(message);
    }
  };

  const handleTogglePinConversation = async (id: string, pinned: boolean) => {
    try {
      await updateConversationMutation.mutateAsync({ conversationId: id, pinned });
      showToast(pinned ? 'Conversation pinned.' : 'Conversation unpinned.');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to update conversation';
      showToast(message);
    }
  };

  const handleLogout = () => {
    controllerRef.current?.abort();
    setConversationId(null);
    setLatency(undefined);
    setSettingsOpen(false);
    setAboutOpen(false);
    logout();
  };

  const handleUpload = () => {
    fileInputRef.current?.click();
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

  const copyToClipboard = async (text: string): Promise<boolean> => {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      try {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.setAttribute('readonly', '');
        textarea.style.position = 'fixed';
        textarea.style.left = '-9999px';
        document.body.appendChild(textarea);
        textarea.select();
        const copied = document.execCommand('copy');
        document.body.removeChild(textarea);
        return copied;
      } catch {
        return false;
      }
    }
  };

  const handleShareConversation = async () => {
    if (messages.length === 0) {
      showToast('Nothing to share yet.');
      return;
    }
    const payload = messages
      .map((entry) => `${entry.role === 'user' ? 'You' : 'Assistant'}: ${entry.content}`)
      .join('\n\n');
    const copied = await copyToClipboard(payload);
    showToast(copied ? 'Conversation copied to clipboard.' : 'Could not copy — check browser permissions.');
  };

  const handleCopyMessage = async (message: ChatMessage) => {
    const copied = await copyToClipboard(message.content);
    showToast(copied ? 'Message copied.' : 'Could not copy message.');
  };

  const handleRegenerate = (assistantMessage: ChatMessage) => {
    const assistantIndex = messages.findIndex((item) => item.id === assistantMessage.id);
    if (assistantIndex <= 0) {
      return;
    }
    for (let i = assistantIndex - 1; i >= 0; i -= 1) {
      if (messages[i].role === 'user') {
        void handleSend(messages[i].content, {
          regeneratePrefix: messages.slice(0, assistantIndex),
        });
        return;
      }
    }
  };

  const handleFeedback = () => {
    // Placeholder for future backend feedback endpoint.
  };

  return (
    <div className="app-shell classic-font flex min-h-0 flex-col overflow-hidden bg-[var(--ui-bg)] text-[var(--phosphor)] md:flex-row">
      <a href="#chat-main" className="skip-link">Skip to chat content</a>
      <Sidebar
        mode={mode}
        onModeChange={setMode}
        onNewChat={() => {
          void handleNewChat();
        }}
        theme={theme}
        conversations={conversations}
        activeConversationId={conversationId ?? ''}
        onSelectConversation={handleSelectConversation}
        onRenameConversation={(id, title) => {
          void handleRenameConversation(id, title);
        }}
        onTogglePinConversation={(id, pinned) => {
          void handleTogglePinConversation(id, pinned);
        }}
        onDeleteConversation={(id) => {
          void handleDeleteConversation(id);
        }}
        sidebarCollapsed={sidebarCollapsed}
        onToggleSidebarCollapsed={() => setSidebarCollapsed((prev) => !prev)}
        user={user}
        onOpenAbout={() => setAboutOpen(true)}
        onLogout={handleLogout}
      />
      <SettingsPanel
        open={settingsOpen}
        theme={theme}
        onSetTheme={setTheme}
        onClose={() => setSettingsOpen(false)}
      />
      <AboutPanel open={aboutOpen} onClose={() => setAboutOpen(false)} />
      <main id="chat-main" aria-busy={isLoading || isBootstrapping} className="classic-atmosphere relative flex min-h-0 flex-1 flex-col border-t border-[var(--ui-border)] bg-[var(--ui-bg)] md:h-full md:border-t-0">
        <ChatHeader
          mode={mode}
          latency={latency}
          isLoading={isLoading}
          conversationTitle={activeConversationTitle}
          settingsOpen={settingsOpen}
          onShareConversation={() => {
            void handleShareConversation();
          }}
          onToggleSettings={() => setSettingsOpen((prev) => !prev)}
        />
        <div ref={messageLogRef} role="log" aria-live="polite" aria-relevant="additions text" className="flex-1 overflow-y-auto px-3 py-2 pb-28 sm:px-4 sm:pb-32">
          <div className="chat-column flex flex-col gap-2">
            {bootstrapError && (
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-200">
                <span>{bootstrapError}</span>
                <button
                  type="button"
                  onClick={handleRetryBootstrap}
                  className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-1.5 text-xs font-medium text-red-100 transition hover:bg-red-500/20"
                >
                  Retry
                </button>
              </div>
            )}
            {messages.length === 0 && (
              <div className="elevated-panel rounded-xl p-4 text-left sm:p-5">
                <div className="text-xs uppercase tracking-[0.2em] text-[var(--phosphor-dim)]">System ready</div>
                <div className="mt-2 text-xl font-semibold leading-snug text-[var(--phosphor-bright)] sm:text-2xl">
                  {mode === 'smart' ? 'Start a smart-routed conversation' : 'Start a direct model conversation'}
                </div>
                <div className="mt-2 text-base leading-relaxed text-[var(--phosphor)]">
                  {mode === 'smart'
                    ? 'Enter a prompt below and Smart mode will choose the right path: quick chat, grounded retrieval, or full workflow orchestration.'
                    : 'Enter a prompt below for fast direct responses. Use Smart mode when you need grounding, deeper analysis, or workflow trace.'}
                </div>
                <div className="mt-3 grid gap-2 text-sm text-[var(--phosphor-dim)] sm:grid-cols-2">
                  <div className="rounded-lg border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] px-3 py-2.5 leading-relaxed">
                    {mode === 'smart'
                      ? 'Smart mode can pull from internal docs and fresh public context.'
                      : 'Great for quick prompts, edits, and low-latency back-and-forth.'}
                  </div>
                  <div className="rounded-lg border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] px-3 py-2.5 leading-relaxed">
                    {mode === 'smart'
                      ? 'When needed, Smart mode returns workflow trace and step updates.'
                      : 'Use Smart mode for sources, retrieval, and multi-agent orchestration.'}
                  </div>
                </div>
              </div>
            )}
            {messages.length > 0 && (
              <VirtualizedMessageList
                scrollRef={messageLogRef}
                messages={messages}
                isLoading={isLoading}
                onCopy={handleCopyMessage}
                onRegenerate={handleRegenerate}
                onFeedback={handleFeedback}
              />
            )}
            <UploadStatusList items={uploadStatuses} />
          </div>
        </div>
        <div className="composer-dock pointer-events-none absolute inset-x-0 bottom-0 z-20 px-3 pb-4 pt-10 sm:px-4 sm:pb-5">
          <div className="chat-column pointer-events-auto">
            <ChatInput
              onSend={handleSend}
              disabled={isLoading || isBootstrapping}
              onAttach={handleUpload}
            />
          </div>
        </div>
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
      {toast && (
        <div
          role="status"
          aria-live="polite"
          className="pointer-events-none fixed bottom-24 left-1/2 z-[60] -translate-x-1/2 rounded-full border border-[var(--ui-border-strong)] bg-[var(--ui-panel-strong)] px-4 py-2 text-sm text-[var(--phosphor-bright)] shadow-lg"
        >
          {toast}
        </div>
      )}
    </div>
  );
}
