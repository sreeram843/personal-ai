import { useEffect, useMemo, useRef, useState } from 'react';
import {
  sendMessage,
  uploadDocuments,
} from './api';
import { ChatHeader } from './components/ChatHeader';
import { ChatInput } from './components/ChatInput';
import { ChatMessageBubble } from './components/ChatMessageBubble';
import { Sidebar } from './components/Sidebar';
import { UploadStatusList } from './components/UploadStatusList';
import { useLocalStorage } from './hooks/useLocalStorage';
import { useTheme } from './hooks/useTheme';
import type { ChatMessage, ConversationMode, UploadStatus } from './types';
import { playPrintTick } from './utils/terminalAudio';

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

export default function App() {
  const [theme, , toggleTheme] = useTheme();
  const [mode, setMode] = useLocalStorage<ConversationMode>('personal-ai-mode', 'rag');
  const [uiMode, setUiMode] = useLocalStorage<'classic' | 'terminal'>('personal-ai-ui-mode', 'classic');
  const [phosphor, setPhosphor] = useLocalStorage<'green' | 'amber'>('personal-ai-phosphor', 'green');
  const [messages, setMessages] = useLocalStorage<ChatMessage[]>('personal-ai-history', []);
  const [uploadStatuses, setUploadStatuses] = useState<UploadStatus[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [latency, setLatency] = useState<number | undefined>(undefined);
  const controllerRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    document.documentElement.setAttribute('data-phosphor', phosphor);
  }, [phosphor]);

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
    let streamed = '';

    try {
      const response = await sendMessage(mode, text, controller.signal, (chunk) => {
        streamed += chunk;
        if (!terminalExperience) {
          setMessages((prev) =>
            prev.map((msg) => (msg.id === assistantMessage.id ? { ...msg, content: streamed } : msg)),
          );
        }
      });

      const elapsed = performance.now() - startedAt;
      setLatency(elapsed);

      const finalMessage = response.message || streamed;

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
    setMessages([]);
    setLatency(undefined);
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

  const activeModel = useMemo(() => (mode === 'rag' ? 'rag-chat (rag_chat)' : 'chat (chat)'), [mode]);
  const isTerminalUI = uiMode === 'terminal';

  return (
    <div className="flex min-h-screen flex-col overflow-hidden bg-[#0d0f0d] text-[var(--phosphor)] md:h-screen md:flex-row">
      <Sidebar
        mode={mode}
        onModeChange={(value) => setMode(value)}
        onNewChat={handleNewChat}
        onUpload={handleUpload}
        theme={theme}
        onToggleTheme={toggleTheme}
        onToggleUI={() => setUiMode((prev) => (prev === 'classic' ? 'terminal' : 'classic'))}
      />
      <main className="flex min-h-0 flex-1 flex-col border-t border-[#007f1f] bg-[#000800] md:h-full md:border-l md:border-t-0">
        <ChatHeader
          mode={mode}
          model={activeModel || DEFAULT_MODEL_NAME}
          latency={latency}
          isLoading={isLoading}
          uiMode={uiMode}
          onToggleUI={() => setUiMode((prev) => (prev === 'classic' ? 'terminal' : 'classic'))}
          phosphor={phosphor}
          onTogglePhosphor={() => setPhosphor((prev) => (prev === 'green' ? 'amber' : 'green'))}
        />
        {isTerminalUI ? (
          <div className="flex h-full flex-1 flex-col bg-[#0b0d0b] p-2 md:p-3">
            <div className="crt-screen phosphor-text terminal-font flex h-full min-h-[28rem] min-w-0 flex-col rounded-md text-xl leading-6 sm:text-2xl sm:leading-7">
              <div className="flex-1 overflow-y-auto px-4 py-4 sm:px-5 sm:py-5">
                {messages.length === 0 ? (
                  <div className="mx-auto flex h-full w-full max-w-4xl items-center justify-center">
                    <div className="w-full max-w-2xl rounded-md border border-[#194119] bg-[rgba(7,20,7,0.72)] px-5 py-6 text-center shadow-[0_0_0_1px_rgba(32,72,32,0.3)] sm:px-8 sm:py-8">
                      <div className="text-[11px] uppercase tracking-[0.45em] text-[var(--phosphor-dim)] sm:text-xs">
                        Terminal Session Ready
                      </div>
                      <div className="mt-3 text-3xl leading-none text-[var(--phosphor-bright)] sm:text-5xl">
                        {mode === 'rag' ? 'RAG MODE ONLINE' : 'STANDARD MODE ONLINE'}
                      </div>
                      <div className="mt-4 text-base leading-6 text-[var(--phosphor)] sm:text-xl sm:leading-7">
                        Ask a question to start a session, or upload documents to ground responses in your own material.
                      </div>
                      <div className="mt-5 grid gap-2 text-left text-sm text-[var(--phosphor-dim)] sm:grid-cols-2 sm:text-base">
                        <div className="rounded border border-[#173417] bg-[rgba(6,14,6,0.55)] px-3 py-2">
                          &gt; Ask for live market, weather, or news data
                        </div>
                        <div className="rounded border border-[#173417] bg-[rgba(6,14,6,0.55)] px-3 py-2">
                          &gt; Switch to RAG after uploading documents
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
                <div ref={bottomRef} />
              </div>

              <div className="border-t border-[var(--phosphor-dim)] px-4 py-3 sm:px-5">
                <ChatInput onSend={handleSend} disabled={isLoading} terminalMode />
              </div>
            </div>
          </div>
        ) : (
          <>
            <div className="flex-1 overflow-y-auto px-4 py-4 sm:px-5 md:px-6">
              <div className="mx-auto flex w-full max-w-4xl flex-col gap-3">
                {messages.length === 0 && (
                  <div className="rounded-xl border border-[#174117] bg-[linear-gradient(180deg,rgba(5,18,5,0.92),rgba(3,12,3,0.82))] p-5 text-left shadow-[0_0_0_1px_rgba(23,65,23,0.35)] sm:p-6">
                    <div className="text-[11px] uppercase tracking-[0.35em] text-[var(--phosphor-dim)]">System Ready</div>
                    <div className="mt-3 text-2xl text-[var(--phosphor-bright)] sm:text-3xl">
                      {mode === 'rag' ? 'Start a grounded conversation' : 'Start a direct model conversation'}
                    </div>
                    <div className="mt-3 max-w-2xl text-sm leading-6 text-[var(--phosphor)] sm:text-base">
                      Enter a prompt below, or upload documents and use RAG mode to answer against your own files.
                    </div>
                    <div className="mt-5 grid gap-3 text-sm text-[var(--phosphor-dim)] sm:grid-cols-2">
                      <div className="rounded-lg border border-[#123312] bg-[#020a02]/80 px-3 py-3">
                        Live queries: weather, FX, stocks, commodities, news.
                      </div>
                      <div className="rounded-lg border border-[#123312] bg-[#020a02]/80 px-3 py-3">
                        Upload text, markdown, or PDF files to ground answers.
                      </div>
                    </div>
                  </div>
                )}
                {messages.map((message, index) => (
                  <ChatMessageBubble
                    key={message.id}
                    message={message}
                    isStreaming={isLoading && index === messages.length - 1}
                  />
                ))}
                <div ref={bottomRef} />
                <UploadStatusList items={uploadStatuses} />
              </div>
            </div>
            <div className="border-t border-[#007f1f] bg-[#001200] px-4 py-4 sm:px-5 md:px-6 md:py-5">
              <div className="mx-auto max-w-4xl">
                <ChatInput onSend={handleSend} disabled={isLoading} />
              </div>
            </div>
          </>
        )}
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
