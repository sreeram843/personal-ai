import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { AuthConfig, CurrentUser } from './api';
import { sendMessage, uploadDocuments } from './api';
import { ChevronDown } from 'lucide-react';
import { AboutPanel } from './components/AboutPanel';
import { SettingsPanel } from './components/SettingsPanel';
import { ChatHeader } from './components/ChatHeader';
import { ChatInput, type ChatInputHandle } from './components/ChatInput';
import { AttachmentDropZone } from './components/AttachmentDropZone';
import { EmptyStateCard } from './components/EmptyStateCard';
import { resolveCuraiLogoState } from './components/curaiLogoState';
import { VirtualizedMessageList } from './components/VirtualizedMessageList';
import { Sidebar } from './components/Sidebar';
import { UploadStatusList } from './components/UploadStatusList';
import { useBodyScrollLock } from './hooks/useBodyScrollLock';
import { useLocalStorage } from './hooks/useLocalStorage';
import { useMessageLogScroll } from './hooks/useMessageLogScroll';
import { useTheme } from './hooks/useTheme';
import { useVisualViewportOffset } from './hooks/useVisualViewport';
import {
  useCreateConversation,
  useDeleteConversation,
  useConversationMessages,
  useConversations,
  useInvalidateConversationData,
  useLogout,
  useUpdateConversation,
} from './query/hooks';
import { fetchAssistants } from './api';
import type { AssistantSummary } from './types';
import {
  appendOptimisticSend,
  messageQueryKey,
  promoteDraftMessages,
  readCachedMessages,
  updateCachedMessage,
  writeCachedMessages,
} from './query/messageCache';
import type { ChatMessage, ConversationMode, ToolPermissionMode, UploadStatus, WorkflowEventPayload } from './types';
import { classifyChatError, isAbortError } from './utils/chatErrors';

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

export default function App({ authConfig, user }: AppProps) {
  const queryClient = useQueryClient();
  const [theme, setTheme] = useTheme();
  const [toolPermissionMode, setToolPermissionMode] = useLocalStorage<ToolPermissionMode>(
    'personal-ai-tool-permission-mode',
    'auto',
  );
  const [mode, setMode] = useLocalStorage<ConversationMode>('personal-ai-mode', 'smart');
  const [selectedAssistantId, setSelectedAssistantId] = useLocalStorage<string>(
    'personal-ai-selected-assistant',
    'default',
  );
  const [assistants, setAssistants] = useState<AssistantSummary[]>([]);
  const [assistantsLoading, setAssistantsLoading] = useState(false);
  const [approvedToolIds, setApprovedToolIds] = useState<string[]>([]);
  const [sidebarCollapsed, setSidebarCollapsed] = useLocalStorage<boolean>('personal-ai-sidebar-collapsed', false);
  const [sidebarWidth, setSidebarWidth] = useLocalStorage<number>('personal-ai-sidebar-width', 270);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [uploadStatuses, setUploadStatuses] = useState<UploadStatus[]>([]);
  const [aboutOpen, setAboutOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [editingUserMessageId, setEditingUserMessageId] = useState<string | null>(null);
  /** Per-conversation abort controllers so switching chats does not cancel in-flight replies. */
  const controllersByConversationRef = useRef<Map<string, AbortController>>(new Map());
  const inflightConversationIdsRef = useRef<Set<string>>(new Set());
  const [inflightVersion, setInflightVersion] = useState(0);
  const viewedConversationIdRef = useRef<string | null>(null);
  const messageLogRef = useRef<HTMLDivElement | null>(null);
  const chatInputRef = useRef<ChatInputHandle | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const bumpInflight = (conversationKey: string, active: boolean) => {
    const set = inflightConversationIdsRef.current;
    if (active) {
      set.add(conversationKey);
    } else {
      set.delete(conversationKey);
    }
    setInflightVersion((value) => value + 1);
  };

  const abortConversationRequest = (conversationKey: string | null | undefined) => {
    if (!conversationKey) {
      return;
    }
    const controller = controllersByConversationRef.current.get(conversationKey);
    if (controller) {
      controller.abort();
      controllersByConversationRef.current.delete(conversationKey);
    }
    bumpInflight(conversationKey, false);
  };

  const authReady = true;
  useEffect(() => {
    if (mode !== 'chat' && mode !== 'smart') {
      setMode('smart');
    }
  }, [mode, setMode]);
  useEffect(() => {
    if (!authReady) {
      return;
    }
    setAssistantsLoading(true);
    fetchAssistants()
      .then(setAssistants)
      .catch(() => setAssistants([]))
      .finally(() => setAssistantsLoading(false));
  }, [authReady]);
  const conversationsQuery = useConversations(authReady);
  const messagesQuery = useConversationMessages(conversationId, authReady);
  const createConversationMutation = useCreateConversation();
  const deleteConversationMutation = useDeleteConversation();
  const updateConversationMutation = useUpdateConversation();
  const logout = useLogout();
  const { invalidateAfterSend } = useInvalidateConversationData();

  useVisualViewportOffset();
  useBodyScrollLock(mobileSidebarOpen);

  const conversations = conversationsQuery.data ?? [];
  const messages = messagesQuery.data ?? [];
  // inflightVersion forces re-render when background chats start/finish generating.
  void inflightVersion;
  const isLoading =
    conversationId != null && inflightConversationIdsRef.current.has(conversationId);
  const lastMessage = messages[messages.length - 1];
  const { showJumpToLatest, jumpToLatest, isNearBottom } = useMessageLogScroll(messageLogRef, [
    messages.length,
    lastMessage?.id,
    lastMessage?.content,
    isLoading,
  ]);

  const bootstrapError = useMemo(() => {
    if (isLoading) {
      return null;
    }
    if (conversationsQuery.isError) {
      return formatQueryError(conversationsQuery.error, 'Failed to load conversations');
    }
    if (messagesQuery.isError) {
      return formatQueryError(messagesQuery.error, 'Failed to load conversation messages');
    }
    return null;
  }, [isLoading, conversationsQuery.isError, conversationsQuery.error, messagesQuery.isError, messagesQuery.error]);

  const isBootstrapping = authReady && conversationsQuery.isLoading && !conversationsQuery.data;

  const logoState = useMemo(() => {
    if (isBootstrapping) {
      return 'thinking';
    }
    return resolveCuraiLogoState({
      isLoading,
      hasBootstrapError: Boolean(bootstrapError),
      messages,
    });
  }, [isBootstrapping, isLoading, bootstrapError, messages]);

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
    viewedConversationIdRef.current = conversationId;
  }, [conversationId]);

  const showToast = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(null), 2200);
  };

  const handleSend = async (
    text: string,
    options?: {
      /** Regenerate: keep existing user turn, replace assistant reply only. */
      regeneratePrefix?: ChatMessage[];
      /** Edit-and-resend: replace user turn and drop all messages after it. */
      editResendPrefix?: ChatMessage[];
      approvedToolIds?: string[];
    },
  ) => {
    if (!text.trim() || isBootstrapping) {
      return;
    }

    const draftLock = '__draft__';
    const startingId = conversationId;
    const lockKey = startingId ?? draftLock;
    if (inflightConversationIdsRef.current.has(lockKey)) {
      return;
    }

    setEditingUserMessageId(null);
    bumpInflight(lockKey, true);
    // Only cancel an in-flight request for *this* conversation (regenerate / resend).
    if (startingId) {
      const prior = controllersByConversationRef.current.get(startingId);
      if (prior) {
        prior.abort();
        controllersByConversationRef.current.delete(startingId);
      }
    }

    let activeConversationId = conversationId;
    if (!activeConversationId) {
      try {
        const created = await createConversationMutation.mutateAsync({
          mode,
          assistantId: selectedAssistantId,
        });
        activeConversationId = created.id;
        const draft = readCachedMessages(queryClient, null);
        if (draft.length > 0) {
          writeCachedMessages(queryClient, created.id, draft);
          queryClient.removeQueries({ queryKey: messageQueryKey(null) });
        }
        bumpInflight(draftLock, false);
        bumpInflight(created.id, true);
        setConversationId(created.id);
      } catch (error) {
        bumpInflight(draftLock, false);
        const message = error instanceof Error ? error.message : 'Failed to start a new conversation';
        showToast(message);
        return;
      }
    }

    let targetConversationId = activeConversationId;
    // IDs that still count as "this send" when the server remaps conversation_id
    // (e.g. create returns new-conversation-id, stream later emits conv-1).
    const originConversationIds = new Set<string>(
      [startingId, activeConversationId].filter((id): id is string => Boolean(id)),
    );
    const isViewingOrigin = () => {
      const viewed = viewedConversationIdRef.current;
      return viewed === null || originConversationIds.has(viewed) || viewed === targetConversationId;
    };

    const isRegenerate = Boolean(options?.regeneratePrefix);
    const isEditResend = Boolean(options?.editResendPrefix);
    const assistantMessage: ChatMessage = {
      id: createId(),
      role: 'assistant',
      content: '',
      createdAt: Date.now(),
    };

    let requestHistory: ChatMessage[];
    if (isRegenerate && options?.regeneratePrefix) {
      requestHistory = options.regeneratePrefix;
      writeCachedMessages(queryClient, targetConversationId, [...requestHistory, assistantMessage]);
    } else if (isEditResend && options?.editResendPrefix) {
      const userMessage: ChatMessage = {
        id: createId(),
        role: 'user',
        content: text,
        createdAt: Date.now(),
      };
      requestHistory = [...options.editResendPrefix, userMessage];
      writeCachedMessages(queryClient, targetConversationId, [...requestHistory, assistantMessage]);
    } else {
      const userMessage: ChatMessage = {
        id: createId(),
        role: 'user',
        content: text,
        createdAt: Date.now(),
      };
      requestHistory = appendOptimisticSend(
        queryClient,
        targetConversationId,
        userMessage,
        assistantMessage,
      );
    }

    const controller = new AbortController();
    controllersByConversationRef.current.set(targetConversationId, controller);
    const startedAt = performance.now();

    const remountController = (fromId: string, toId: string) => {
      const owned = controllersByConversationRef.current.get(fromId);
      if (owned === controller) {
        controllersByConversationRef.current.delete(fromId);
        controllersByConversationRef.current.set(toId, controller);
      }
      if (inflightConversationIdsRef.current.has(fromId)) {
        bumpInflight(fromId, false);
        bumpInflight(toId, true);
      }
    };

    const adoptConversationId = (nextId: string) => {
      if (targetConversationId === nextId) {
        return;
      }
      const fromId = targetConversationId;
      const pending = readCachedMessages(queryClient, fromId);
      if (pending.length > 0) {
        writeCachedMessages(queryClient, nextId, pending);
      }
      promoteDraftMessages(queryClient, nextId);
      remountController(fromId, nextId);
      originConversationIds.add(fromId);
      originConversationIds.add(nextId);
      targetConversationId = nextId;
      if (isViewingOrigin()) {
        setConversationId(nextId);
      }
    };

    try {
      const response = await sendMessage(
        mode,
        text,
        requestHistory,
        targetConversationId,
        controller.signal,
        (event: WorkflowEventPayload) => {
        if (event.type === 'conversation' && event.conversation_id) {
          adoptConversationId(event.conversation_id);
          return;
        }

        if (event.type === 'workflow' && event.workflow) {
          updateCachedMessage(queryClient, targetConversationId, assistantMessage.id, (msg) => ({
            ...msg,
            workflow: event.workflow,
          }));
          return;
        }

        if (event.type === 'memory' && event.summary && event.phase) {
          const phase = event.phase;
          const summary = event.summary;
          updateCachedMessage(queryClient, targetConversationId, assistantMessage.id, (msg) => ({
            ...msg,
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
          updateCachedMessage(queryClient, targetConversationId, assistantMessage.id, (msg) => ({
            ...msg,
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

        if (event.type === 'block' && event.block) {
          updateCachedMessage(queryClient, targetConversationId, assistantMessage.id, (msg) => ({
            ...msg,
            showLiveSkeleton: false,
            blocks: [...(msg.blocks ?? []), event.block!],
          }));
        }
      },
        {
          toolPermissionMode,
          approvedToolIds: options?.approvedToolIds ?? approvedToolIds,
        },
      );

      const elapsed = performance.now() - startedAt;

      const finalMessage = response.message;
      let nextConversationId = response.conversation_id ?? targetConversationId;

      if (response.conversation_id) {
        adoptConversationId(response.conversation_id);
        nextConversationId = response.conversation_id;
      }

      updateCachedMessage(queryClient, nextConversationId, assistantMessage.id, (msg) => ({
        ...msg,
        content: finalMessage,
        latencyMs: response.latency_ms ?? elapsed,
        sources: response.sources,
        workflow: response.workflow,
        reasoning: response.reasoning,
        sentiment: response.sentiment,
        outputTokens: response.completion_tokens,
        blocks: response.blocks,
        plannedTools: response.planned_tools,
        pendingToolApprovals: response.pending_tool_approvals,
        toolPermissionMode: response.tool_permission_mode,
        showLiveSkeleton: false,
      }));

      const lastUserMessage = [...requestHistory].reverse().find((item) => item.role === 'user');
      if (lastUserMessage && response.prompt_tokens !== undefined) {
        updateCachedMessage(queryClient, nextConversationId, lastUserMessage.id, (msg) => ({
          ...msg,
          inputTokens: response.prompt_tokens,
        }));
      }

      invalidateAfterSend(nextConversationId);
    } catch (error) {
      const cacheId = targetConversationId;
      if (isAbortError(error)) {
        writeCachedMessages(queryClient, cacheId, requestHistory);
        return;
      }
      const { kind, detail } = classifyChatError(error);
      writeCachedMessages(queryClient, cacheId, [
        ...requestHistory,
        {
          ...assistantMessage,
          content: '',
          errorKind: kind,
          errorDetail: detail,
          showLiveSkeleton: false,
        },
      ]);
    } finally {
      if (controllersByConversationRef.current.get(targetConversationId) === controller) {
        controllersByConversationRef.current.delete(targetConversationId);
      }
      bumpInflight(targetConversationId, false);
      bumpInflight(draftLock, false);
      if (viewedConversationIdRef.current === targetConversationId) {
        requestAnimationFrame(() => {
          chatInputRef.current?.focus();
        });
      }
    }
  };

  const handleNewChat = async () => {
    abortConversationRequest(conversationId);
    writeCachedMessages(queryClient, null, []);

    try {
      const created = await createConversationMutation.mutateAsync({
        mode,
        assistantId: selectedAssistantId,
      });
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

  const handleSelectStarterPrompt = (prompt: string) => {
    chatInputRef.current?.setValue(prompt);
  };

  const handleSelectConversation = (id: string) => {
    // Do not abort — let the previous chat finish in the background.
    setConversationId(id);
    setMobileSidebarOpen(false);
  };

  const activeAssistantName = useMemo(() => {
    const active = conversations.find((item) => item.id === conversationId);
    const assistantId = active?.assistantId ?? selectedAssistantId;
    const match = assistants.find((item) => item.id === (assistantId || 'default'));
    return match?.name ?? 'CurAI';
  }, [assistants, conversationId, conversations, selectedAssistantId]);

  const activeConversationTitle = useMemo(() => {
    const active = conversations.find((item) => item.id === conversationId);
    if (active?.title && active.title !== 'New conversation') {
      return active.title;
    }
    return deriveConversationTitle(messages);
  }, [conversationId, conversations, messages]);

  const handleDeleteConversation = async (id: string) => {
    abortConversationRequest(id);
    const deletingActive = conversationId === id;
    if (deletingActive) {
      writeCachedMessages(queryClient, null, []);
      setConversationId(null);
    }
    try {
      await deleteConversationMutation.mutateAsync(id);
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
    for (const id of [...controllersByConversationRef.current.keys()]) {
      abortConversationRequest(id);
    }
    setConversationId(null);
    setAboutOpen(false);
    logout();
  };

  const uploadsInFlight = uploadStatuses.some((item) =>
    item.status === 'uploading' || item.status === 'queued' || item.status === 'processing',
  );

  const handleUpload = () => {
    fileInputRef.current?.click();
  };

  const onFilesSelected = async (files: FileList | File[] | null) => {
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
      await uploadDocuments(Array.from(files), {
        onJobStatus: (status) => {
          const mapped: UploadStatus['status'] =
            status === 'queued' ? 'queued' : status === 'in_progress' ? 'processing' : 'uploading';
          setUploadStatuses((prev) =>
            prev.map((item) =>
              items.some((it) => it.id === item.id)
                ? {
                    ...item,
                    status: mapped,
                  }
                : item,
            ),
          );
        },
      });
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
      const names = items.map((item) => item.name).join(', ');
      showToast(
        items.length === 1
          ? `Uploaded ${names}. Ask about it (Smart mode works best for summaries).`
          : `Uploaded ${items.length} files. Ask about them in chat.`,
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
      showToast(message);
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

  const handleStop = () => {
    abortConversationRequest(conversationId);
  };

  const handleRetry = (assistantMessage: ChatMessage) => {
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

  const handleEditResend = (userMessage: ChatMessage, newContent: string) => {
    const userIndex = messages.findIndex((item) => item.id === userMessage.id);
    if (userIndex < 0) {
      return;
    }
    void handleSend(newContent, {
      editResendPrefix: messages.slice(0, userIndex),
    });
  };

  const handleEditFromError = (assistantMessage: ChatMessage) => {
    const assistantIndex = messages.findIndex((item) => item.id === assistantMessage.id);
    if (assistantIndex <= 0) {
      return;
    }
    for (let i = assistantIndex - 1; i >= 0; i -= 1) {
      if (messages[i].role === 'user') {
        setEditingUserMessageId(messages[i].id);
        return;
      }
    }
  };

  const handleCopyMessage = async (message: ChatMessage) => {
    const text =
      message.errorDetail?.trim() ||
      message.content.trim() ||
      message.content;
    const copied = await copyToClipboard(text);
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

  const handleApproveTools = (toolIds: string[]) => {
    const merged = [...new Set([...approvedToolIds, ...toolIds])];
    setApprovedToolIds(merged);
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      if (messages[i].role !== 'user') {
        continue;
      }
      void handleSend(messages[i].content, {
        regeneratePrefix: messages.slice(0, i + 1),
        approvedToolIds: merged,
      });
      return;
    }
  };

  return (
    <div className="app-shell classic-font flex min-h-0 flex-col overflow-hidden bg-[var(--ui-bg)] text-[var(--phosphor)] md:flex-row">
      <a href="#chat-main" className="skip-link">Skip to chat content</a>
      <Sidebar
        onNewChat={() => {
          setMobileSidebarOpen(false);
          void handleNewChat();
        }}
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
        sidebarWidth={sidebarWidth}
        onSidebarWidthChange={setSidebarWidth}
        user={user}
        onOpenAbout={() => {
          setMobileSidebarOpen(false);
          setAboutOpen(true);
        }}
        onOpenSettings={() => {
          setMobileSidebarOpen(false);
          setSettingsOpen(true);
        }}
        onLogout={handleLogout}
        mobileOpen={mobileSidebarOpen}
        onMobileClose={() => setMobileSidebarOpen(false)}
      />
      <AboutPanel open={aboutOpen} onClose={() => setAboutOpen(false)} />
      <SettingsPanel
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        user={user}
        authConfig={authConfig}
        theme={theme}
        onSetTheme={setTheme}
        toolPermissionMode={toolPermissionMode}
        onToolPermissionModeChange={setToolPermissionMode}
        onAccountDeleted={handleLogout}
      />
      <main id="chat-main" aria-busy={isLoading || isBootstrapping} className="classic-atmosphere relative flex min-h-0 flex-1 flex-col overflow-hidden border-t border-[var(--ui-border)] bg-[var(--ui-bg)] md:h-full md:border-t-0">
        <ChatHeader
          mode={mode}
          logoState={logoState}
          conversationTitle={activeConversationTitle}
          assistantName={activeAssistantName}
          onOpenSidebar={() => setMobileSidebarOpen(true)}
        />
        <div
          ref={messageLogRef}
          role="log"
          aria-live="polite"
          aria-relevant="additions text"
          className="message-log flex-1 px-3 py-2 pb-32 sm:px-4 sm:pb-36"
        >
          <div className="chat-column flex flex-col gap-2">
            {bootstrapError && (
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[rgba(239,68,68,0.35)] bg-[rgba(239,68,68,0.1)] px-4 py-3 text-sm text-[#f87171]">
                <span>{bootstrapError}</span>
                <button
                  type="button"
                  onClick={handleRetryBootstrap}
                  className="rounded-lg border border-[rgba(239,68,68,0.35)] bg-[rgba(239,68,68,0.15)] px-3 py-1.5 text-xs font-semibold text-[#f87171] transition hover:bg-[rgba(239,68,68,0.25)]"
                >
                  Retry
                </button>
              </div>
            )}
            {messages.length === 0 && !isLoading && (
              <EmptyStateCard mode={mode} onSelectPrompt={handleSelectStarterPrompt} />
            )}
            {messages.length > 0 && (
              <VirtualizedMessageList
                scrollRef={messageLogRef}
                messages={messages}
                isLoading={isLoading}
                isNearBottom={isNearBottom}
                editingUserMessageId={editingUserMessageId}
                onCopy={handleCopyMessage}
                onEditResend={handleEditResend}
                onEditCancel={() => setEditingUserMessageId(null)}
                onEditFromError={handleEditFromError}
                onRegenerate={handleRegenerate}
                onRetry={handleRetry}
                onFeedback={handleFeedback}
                onApproveTools={handleApproveTools}
              />
            )}
            <UploadStatusList items={uploadStatuses} />
          </div>
        </div>
        <div className="composer-dock pointer-events-none absolute inset-x-0 z-20 px-3 pt-10 sm:px-4">
          <div className="composer-column pointer-events-auto">
            {showJumpToLatest && (
              <div className="mb-2 flex justify-center">
                <button
                  type="button"
                  onClick={jumpToLatest}
                  className="jump-to-latest pointer-events-auto inline-flex items-center gap-1.5 rounded-full border border-[var(--ui-border)] bg-[var(--ui-panel-strong)] px-3 py-1.5 text-xs font-medium text-[var(--phosphor)] shadow-lg transition hover:bg-[var(--ui-bg-elevated)]"
                >
                  <ChevronDown className="h-3.5 w-3.5" aria-hidden />
                  Jump to latest
                </button>
              </div>
            )}
            <AttachmentDropZone disabled={isBootstrapping || uploadsInFlight} onFiles={onFilesSelected}>
              <ChatInput
                ref={chatInputRef}
                onSend={handleSend}
                onStop={handleStop}
                isStreaming={isLoading}
                disabled={isBootstrapping || uploadsInFlight}
                onAttach={handleUpload}
                onFilesPasted={onFilesSelected}
                mode={mode}
                onModeChange={setMode}
                assistants={assistants}
                selectedAssistantId={selectedAssistantId}
                onSelectAssistant={setSelectedAssistantId}
                assistantsLoading={assistantsLoading}
              />
            </AttachmentDropZone>
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
          className="mobile-toast pointer-events-none fixed left-1/2 z-[60] -translate-x-1/2 rounded-full border border-[var(--ui-border-strong)] bg-[var(--ui-panel-strong)] px-4 py-2 text-sm text-[var(--phosphor-bright)] shadow-lg"
        >
          {toast}
        </div>
      )}
    </div>
  );
}
