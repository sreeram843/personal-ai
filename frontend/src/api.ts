import { authHeaders, clearAuthToken, getAuthToken, setAuthToken } from './auth';
import type {
  ChatMessage,
  ChatResponsePayload,
  ConversationMode,
  RetrievedSource,
  WorkflowEventPayload,
} from './types';

export interface ServerConversationSummary {
  id: string;
  title?: string | null;
  mode?: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
  pinned?: boolean;
  pinned_at?: string | null;
}

export interface ServerStoredMessage {
  id: string;
  role: 'system' | 'user' | 'assistant';
  content: string;
  metadata?: Record<string, unknown>;
  created_at: string;
}

export interface AuthConfig {
  auth_disabled: boolean;
  google_client_id: string | null;
  google_auth_enabled: boolean;
}

export interface CurrentUser {
  id: string;
  email?: string | null;
  display_name?: string | null;
}

export interface TokenResponsePayload {
  access_token: string;
  token_type: string;
  user_id: string;
}

function resolveBaseUrl(): string {
  const configured = ((import.meta.env.VITE_API_BASE_URL as string) || '').trim();

  if (!configured) {
    return '';
  }

  if (typeof window === 'undefined') {
    return configured;
  }

  const host = window.location.hostname;
  const isLocalHost = host === 'localhost' || host === '127.0.0.1';
  const configuredIsLocal = configured.includes('localhost') || configured.includes('127.0.0.1');

  if (!isLocalHost && configuredIsLocal) {
    return '';
  }

  return configured;
}

const BASE_URL = resolveBaseUrl();

function isRetryableNetworkError(error: unknown): boolean {
  if (!(error instanceof Error)) {
    return false;
  }
  const message = error.message.toLowerCase();
  return message.includes('load failed') || message.includes('networkerror') || message.includes('failed to fetch');
}

async function safeFetch(input: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(input, init);
  } catch (error) {
    const shouldRetrySameOrigin = BASE_URL !== '' && isRetryableNetworkError(error);
    if (!shouldRetrySameOrigin) {
      throw error;
    }

    const pathname = new URL(input).pathname;
    return fetch(pathname, init);
  }
}

async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const auth = authHeaders();
  Object.entries(auth).forEach(([key, value]) => {
    headers.set(key, value);
  });

  if (init.body && !headers.has('Content-Type') && typeof init.body === 'string') {
    headers.set('Content-Type', 'application/json');
  }

  const response = await safeFetch(`${BASE_URL}${path}`, {
    ...init,
    headers,
  });

  if (!response.ok) {
    const errorText = await response.text();
    if (response.status === 401) {
      clearAuthToken();
    }
    throw new Error(errorText || response.statusText);
  }

  return response;
}

export async function fetchAuthConfig(): Promise<AuthConfig> {
  const response = await safeFetch(`${BASE_URL}/auth/config`, {
    method: 'GET',
  });
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || 'Failed to load auth configuration');
  }
  return (await response.json()) as AuthConfig;
}

export async function fetchCurrentUser(): Promise<CurrentUser> {
  const response = await apiFetch('/auth/me');
  return (await response.json()) as CurrentUser;
}

export async function exchangeGoogleToken(idToken: string): Promise<TokenResponsePayload> {
  const response = await safeFetch(`${BASE_URL}/auth/google`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id_token: idToken }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    let message = errorText || 'Google sign-in failed';
    try {
      const parsed = JSON.parse(errorText) as { detail?: string };
      if (parsed.detail) {
        message = parsed.detail;
      }
    } catch {
      // keep raw text
    }
    throw new Error(message);
  }

  const payload = (await response.json()) as TokenResponsePayload;
  setAuthToken(payload.access_token);
  return payload;
}

export async function ensureAuthToken(): Promise<string> {
  const existing = getAuthToken();
  if (existing) {
    return existing;
  }

  const response = await safeFetch(`${BASE_URL}/auth/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || 'Failed to obtain auth token');
  }

  const payload = (await response.json()) as { access_token: string };
  setAuthToken(payload.access_token);
  return payload.access_token;
}

export async function listConversations(): Promise<ServerConversationSummary[]> {
  const response = await apiFetch('/conversations');
  const payload = (await response.json()) as { conversations: ServerConversationSummary[] };
  return payload.conversations;
}

export async function createConversation(mode: ConversationMode, title?: string): Promise<ServerConversationSummary> {
  const response = await apiFetch('/conversations', {
    method: 'POST',
    body: JSON.stringify({
      title,
      mode,
    }),
  });
  return (await response.json()) as ServerConversationSummary;
}

export async function fetchConversationMessages(conversationId: string): Promise<ServerStoredMessage[]> {
  const response = await apiFetch(`/conversations/${conversationId}/messages`);
  const payload = (await response.json()) as { messages: ServerStoredMessage[] };
  return payload.messages;
}

export async function deleteConversation(conversationId: string): Promise<void> {
  await apiFetch(`/conversations/${conversationId}`, { method: 'DELETE' });
}

export interface UpdateConversationPayload {
  title?: string;
  pinned?: boolean;
}

export async function updateConversation(
  conversationId: string,
  payload: UpdateConversationPayload,
): Promise<ServerConversationSummary> {
  const response = await apiFetch(`/conversations/${conversationId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
  return (await response.json()) as ServerConversationSummary;
}

export function mapServerMessage(message: ServerStoredMessage): ChatMessage {
  const metadata = message.metadata ?? {};
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    createdAt: new Date(message.created_at).getTime(),
    sources: Array.isArray(metadata.sources) ? (metadata.sources as RetrievedSource[]) : undefined,
    workflow: metadata.workflow as ChatMessage['workflow'],
  };
}

async function streamSseEvents(
  response: Response,
  onEvent: (event: WorkflowEventPayload) => void,
): Promise<void> {
  if (!response.body) {
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split('\n\n');
    buffer = frames.pop() || '';

    for (const frame of frames) {
      const payload = frame
        .split('\n')
        .filter((line) => line.startsWith('data:'))
        .map((line) => line.slice(5).trim())
        .join('\n');

      if (!payload) {
        continue;
      }

      onEvent(JSON.parse(payload) as WorkflowEventPayload);
    }
  }
}

export async function sendMessage(
  mode: ConversationMode,
  message: string,
  history: ChatMessage[],
  conversationId: string | null,
  signal: AbortSignal,
  onWorkflowEvent?: (event: WorkflowEventPayload) => void,
): Promise<ChatResponsePayload> {
  const endpoint = mode === 'smart' ? '/smart_chat/stream' : '/chat';
  const url = `${BASE_URL}${endpoint}`;

  const messages = [
    ...history.map((item) => ({ role: item.role, content: item.content })),
    { role: 'user' as const, content: message },
  ];

  const bodyPayload: Record<string, unknown> =
    mode === 'smart'
      ? {
          messages,
          workflow: {
            enabled: true,
            use_rag: true,
            include_trace: true,
            persist_memory: true,
            max_steps: 6,
          },
        }
      : {
          messages,
        };

  if (conversationId) {
    bodyPayload.conversation_id = conversationId;
  }

  const response = await safeFetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
    body: JSON.stringify(bodyPayload),
    signal,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || response.statusText);
  }

  if (response.headers.get('content-type')?.includes('text/event-stream')) {
    let finalResponse: ChatResponsePayload | undefined;
    await streamSseEvents(response, (event) => {
      onWorkflowEvent?.(event);
      if (event.type === 'final' && event.response) {
        finalResponse = event.response;
      }
    });
    if (!finalResponse) {
      throw new Error('Workflow stream completed without a final response');
    }
    const responsePayload = finalResponse as ChatResponsePayload;
    if (responsePayload.sources) {
      responsePayload.sources = normalizeSources(responsePayload.sources);
    }
    return responsePayload;
  }

  if (response.headers.get('content-type')?.includes('application/json')) {
    const data = (await response.json()) as ChatResponsePayload;
    if (data.sources && mode === 'smart') {
      data.sources = normalizeSources(data.sources);
    }
    return data;
  }

  const fallbackText = await response.text();
  return { message: fallbackText };
}

function normalizeSources(sources: RetrievedSource[]): RetrievedSource[] {
  return sources.map((source) => ({
    ...source,
    id: String(source.id ?? ''),
  }));
}

async function readFileAsText(file: File): Promise<string> {
  if (file.name.toLowerCase().endsWith('.pdf') || file.type === 'application/pdf') {
    throw new Error('PDF upload is not supported yet. Use .txt or .md files.');
  }
  return file.text();
}

export async function uploadDocuments(files: File[]): Promise<void> {
  const documents = await Promise.all(
    files.map(async (file) => ({
      text: await readFileAsText(file),
      metadata: {
        path: file.name,
        title: file.name,
      },
    })),
  );

  const response = await apiFetch('/ingest', {
    method: 'POST',
    body: JSON.stringify({ documents }),
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || 'Upload failed');
  }

  const payload = (await response.json()) as { count?: number; job_id?: string; status?: string };
  if (payload.job_id) {
    await pollBackgroundJob(payload.job_id);
    return;
  }
}

async function pollBackgroundJob(jobId: string, timeoutMs = 120_000): Promise<void> {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const response = await apiFetch(`/jobs/${jobId}`);
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || 'Failed to check ingest job status');
    }
    const job = (await response.json()) as { status?: string; error?: string };
    if (job.status === 'completed') {
      return;
    }
    if (job.status === 'failed') {
      throw new Error(job.error || 'Background ingest failed');
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error('Background ingest timed out');
}
