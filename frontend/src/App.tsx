import { useEffect, useMemo, useRef, useState } from 'react';
import {
  getActivePersona,
  getPersonaList,
  getPersonaPreview,
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
import type { ChatMessage, ConversationMode, PersonaPreviewPayload, UploadStatus } from './types';
import { X } from 'lucide-react';

function createId() {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2);
}

const DEFAULT_MODEL_NAME = 'local-ollama';

export default function App() {
  const [theme, , toggleTheme] = useTheme();
  const [mode, setMode] = useLocalStorage<ConversationMode>('personal-ai-mode', 'rag');
  const [messages, setMessages] = useLocalStorage<ChatMessage[]>('personal-ai-history', []);
  const [uploadStatuses, setUploadStatuses] = useState<UploadStatus[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [latency, setLatency] = useState<number | undefined>(undefined);
  const [persona, setPersona] = useState<string>('harvey_specter');
  const [personaOptions, setPersonaOptions] = useState<string[]>([]);
  const [personaPreview, setPersonaPreview] = useState<PersonaPreviewPayload | null>(null);
  const [isPersonaSwitching, setIsPersonaSwitching] = useState(false);
  const controllerRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    const bootstrap = async () => {
      try {
        const [list, active, preview] = await Promise.all([
          getPersonaList(),
          getActivePersona(),
          getPersonaPreview(),
        ]);
        setPersonaOptions(list);
        setPersona(active);
        setPersonaPreview(preview);
      } catch (error) {
        console.warn('Persona bootstrap failed', error);
      }
    };
    bootstrap();
  }, []);

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

    const controller = new AbortController();
    controllerRef.current = controller;
    const startedAt = performance.now();
    let streamed = '';

    try {
      const response = await sendMessage(mode, text, controller.signal, (chunk) => {
        streamed += chunk;
        setMessages((prev) =>
          prev.map((msg) => (msg.id === assistantMessage.id ? { ...msg, content: streamed } : msg)),
        );
      });

      const elapsed = performance.now() - startedAt;
      setLatency(elapsed);
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessage.id
            ? {
                ...msg,
                content: response.message || streamed,
                latencyMs: elapsed,
                sources: response.sources,
              }
            : msg,
        ),
      );
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

  const handlePersonaPreview = async () => {
    try {
      const preview = await getPersonaPreview();
      setPersonaPreview(preview);
    } catch (error) {
      console.error('Failed to load persona preview', error);
    }
  };

  const handlePersonaChange = async (value: string) => {
    if (!value || value === persona) {
      return;
    }
    setIsPersonaSwitching(true);
    try {
      await switchPersona(value);
      setPersona(value);
      handleNewChat();
      await handlePersonaPreview();
    } catch (error) {
      console.error('Failed to switch persona', error);
    } finally {
      setIsPersonaSwitching(false);
    }
  };

  const activeModel = useMemo(() => (mode === 'rag' ? 'rag-chat (rag_chat)' : 'chat (chat)'), [mode]);

  return (
    <div className="flex h-screen overflow-hidden bg-gray-100 text-gray-900 dark:bg-zinc-950 dark:text-zinc-100">
        <Sidebar
          mode={mode}
          onModeChange={(value) => setMode(value)}
          onNewChat={handleNewChat}
          onUpload={handleUpload}
          theme={theme}
          onToggleTheme={toggleTheme}
          persona={persona}
          personaOptions={personaOptions.length > 0 ? personaOptions : [persona]}
          onPersonaChange={handlePersonaChange}
          onPersonaPreview={handlePersonaPreview}
          personaDisabled={isPersonaSwitching}
        />
        <main className="flex h-full flex-1 flex-col">
          <ChatHeader
            mode={mode}
            model={activeModel || DEFAULT_MODEL_NAME}
            latency={latency}
            isLoading={isLoading || isPersonaSwitching}
            persona={persona}
          />
          <div className="flex-1 overflow-y-auto bg-gradient-to-b from-white/90 to-gray-100/60 px-6 py-6 dark:from-zinc-900/80 dark:to-zinc-950">
            <div className="mx-auto flex w-full max-w-3xl flex-col gap-4">
              {personaPreview && (
                <div className="rounded-3xl border border-emerald-200 bg-white/90 p-4 text-sm text-gray-700 shadow dark:border-emerald-400/40 dark:bg-zinc-900/80 dark:text-zinc-200">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-xs font-semibold uppercase tracking-wide text-emerald-500">
                        Persona
                      </div>
                      <div className="text-base font-semibold text-gray-900 dark:text-zinc-100">
                        {personaPreview.persona} · fewshots {personaPreview.fewshots}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => setPersonaPreview(null)}
                      className="rounded-full border border-transparent p-1 text-gray-400 transition hover:text-gray-600 dark:text-zinc-500 dark:hover:text-zinc-300"
                      title="Close"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                  <div className="mt-3 max-h-48 overflow-y-auto whitespace-pre-wrap leading-relaxed text-xs">
                    {personaPreview.system_prompt}
                  </div>
                </div>
              )}
              {messages.length === 0 && (
                <div className="rounded-3xl border border-dashed border-gray-300 bg-white/70 p-6 text-center text-sm text-gray-500 dark:border-zinc-700 dark:bg-zinc-900/70 dark:text-zinc-400">
                  Start by asking a question or upload reference documents for RAG mode.
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
          <div className="border-t border-gray-200 bg-gray-50 px-6 py-6 dark:border-zinc-800 dark:bg-zinc-900">
            <div className="mx-auto max-w-3xl">
              <ChatInput onSend={handleSend} disabled={isLoading} />
              <p className="mt-2 text-xs text-gray-400">
                Shift + Enter for newline. Voice input uses your browser speech recognition.
              </p>
            </div>
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
