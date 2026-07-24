import { authHeaders, clearAuthToken, getAuthToken, setAuthToken } from './auth';
import { isCapacitorNative } from './platform/capacitor';
import { resolveApiBaseUrl } from './platform/resolveApiBaseUrl';
import { createChatRequestError } from './utils/chatErrors';
import type { ContentBlock } from './types/liveData';
import type {
  ChatErrorKind,
  ChatMessage,
  ChatResponsePayload,
  ConversationMode,
  DemoChatRequestPayload,
  DemoChatResponsePayload,
  DemoConfig,
  RetrievedSource,
  WorkflowEventPayload,
  AgentSendOptions,
  McpServerSummary,
  McpServerTestResult,
  DoctorReport,
  SkillSummary,
  AgentTaskSummary,
  AssistantSummary,
} from './types';

export interface ServerConversationSummary {
  id: string;
  title?: string | null;
  mode?: string | null;
  assistant_id?: string | null;
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

function getBaseUrl(): string {
  const configured = ((import.meta.env.VITE_API_BASE_URL as string) || '').trim();

  if (typeof window === 'undefined') {
    return resolveApiBaseUrl({
      configuredBaseUrl: configured,
      hostname: 'localhost',
      isNativeShell: false,
    });
  }

  return resolveApiBaseUrl({
    configuredBaseUrl: configured,
    hostname: window.location.hostname,
    isNativeShell: isCapacitorNative(),
  });
}

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
    const baseUrl = getBaseUrl();
    const shouldRetrySameOrigin =
      baseUrl !== '' &&
      !isCapacitorNative() &&
      isRetryableNetworkError(error);

    if (!shouldRetrySameOrigin) {
      throw error;
    }

    let pathname: string;
    try {
      pathname = new URL(input).pathname;
    } catch {
      throw error;
    }

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

  const response = await safeFetch(`${getBaseUrl()}${path}`, {
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
  const response = await safeFetch(`${getBaseUrl()}/auth/config`, {
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
  const response = await safeFetch(`${getBaseUrl()}/auth/google`, {
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

  const response = await safeFetch(`${getBaseUrl()}/auth/token`, {
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

export async function createConversation(
  mode: ConversationMode = 'smart',
  title?: string,
  assistantId?: string | null,
): Promise<ServerConversationSummary> {
  const response = await apiFetch('/conversations', {
    method: 'POST',
    body: JSON.stringify({
      title,
      mode,
      assistant_id: assistantId && assistantId !== 'default' ? assistantId : undefined,
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

function readTokenCount(metadata: Record<string, unknown>, ...keys: string[]): number | undefined {
  for (const key of keys) {
    const raw = metadata[key];
    if (typeof raw === 'number' && Number.isFinite(raw)) {
      return raw;
    }
  }
  return undefined;
}

function readString(metadata: Record<string, unknown>, key: string): string | undefined {
  const raw = metadata[key];
  return typeof raw === 'string' ? raw : undefined;
}

function readErrorKind(metadata: Record<string, unknown>): ChatErrorKind | undefined {
  const raw = metadata.error_kind ?? metadata.errorKind;
  if (
    raw === 'network' ||
    raw === 'timeout' ||
    raw === 'rate_limit' ||
    raw === 'refused' ||
    raw === 'unknown'
  ) {
    return raw;
  }
  return undefined;
}

function readBlocks(metadata: Record<string, unknown>): ContentBlock[] | undefined {
  return normalizeContentBlocks(metadata.blocks);
}

export function mapServerMessage(message: ServerStoredMessage): ChatMessage {
  const metadata = message.metadata ?? {};
  const rawLatency = metadata.latency_ms ?? metadata.latencyMs;
  const latencyMs = typeof rawLatency === 'number' && Number.isFinite(rawLatency) ? rawLatency : undefined;
  const errorKind = readErrorKind(metadata);
  const errorDetail = readString(metadata, 'error_detail') ?? readString(metadata, 'errorDetail');
  const base = {
    id: message.id,
    role: message.role,
    content: message.content,
    createdAt: new Date(message.created_at).getTime(),
    latencyMs,
    sources: Array.isArray(metadata.sources) ? (metadata.sources as RetrievedSource[]) : undefined,
    workflow: metadata.workflow as ChatMessage['workflow'],
    reasoning: typeof metadata.reasoning === 'string' ? metadata.reasoning : undefined,
    sentiment: typeof metadata.sentiment === 'string' ? metadata.sentiment : undefined,
    errorKind,
    errorDetail,
    blocks: readBlocks(metadata),
  };
  if (message.role === 'user') {
    return {
      ...base,
      inputTokens: readTokenCount(metadata, 'prompt_tokens', 'inputTokens', 'input_tokens'),
    };
  }
  return {
    ...base,
    outputTokens: readTokenCount(metadata, 'completion_tokens', 'outputTokens', 'output_tokens'),
    inputTokens: readTokenCount(metadata, 'prompt_tokens', 'inputTokens', 'input_tokens'),
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

export function buildChatRequestMessages(
  history: ChatMessage[],
  message: string,
): Array<{ role: ChatMessage['role']; content: string }> {
  const trimmed = message.trim();
  const apiHistory = history
    .filter((item) => item.content.trim().length > 0)
    .map((item) => ({ role: item.role, content: item.content }));

  const last = apiHistory[apiHistory.length - 1];
  if (last?.role === 'user' && last.content === trimmed) {
    return apiHistory;
  }

  return [...apiHistory, { role: 'user' as const, content: trimmed }];
}

export async function sendMessage(
  mode: ConversationMode,
  message: string,
  history: ChatMessage[],
  conversationId: string | null,
  signal: AbortSignal,
  onWorkflowEvent?: (event: WorkflowEventPayload) => void,
  agentOptions?: AgentSendOptions,
): Promise<ChatResponsePayload> {
  const endpoint = mode === 'smart' ? '/smart_chat/stream' : '/chat/stream';
  const url = `${getBaseUrl()}${endpoint}`;

  const messages = buildChatRequestMessages(history, message);

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

  bodyPayload.options = {
    tool_permission_mode: agentOptions?.toolPermissionMode ?? 'auto',
    approved_tool_ids: agentOptions?.approvedToolIds ?? [],
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
    throw createChatRequestError(response.status, errorText || response.statusText);
  }

  if (response.headers.get('content-type')?.includes('text/event-stream')) {
    let finalResponse: ChatResponsePayload | undefined;
    await streamSseEvents(response, (event) => {
      onWorkflowEvent?.(event);
      if (event.type === 'error' && event.message) {
        throw new Error(event.message);
      }
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
    responsePayload.blocks = normalizeContentBlocks(responsePayload.blocks);
    return responsePayload;
  }

  if (response.headers.get('content-type')?.includes('application/json')) {
    const data = (await response.json()) as ChatResponsePayload;
    if (data.sources) {
      data.sources = normalizeSources(data.sources);
    }
    data.blocks = normalizeContentBlocks(data.blocks);
    return data;
  }

  const fallbackText = await response.text();
  return { message: fallbackText };
}

function normalizeContentBlocks(blocks: unknown): ContentBlock[] | undefined {
  if (!Array.isArray(blocks)) {
    return undefined;
  }
  return blocks
    .filter((item): item is Record<string, unknown> => Boolean(item && typeof item === 'object'))
    .map((item) => ({
      type: String(item.type ?? '') as ContentBlock['type'],
      data: (item.data as Record<string, unknown>) ?? {},
      subscription_key:
        typeof item.subscription_key === 'string'
          ? item.subscription_key
          : typeof item.subscriptionKey === 'string'
            ? item.subscriptionKey
            : null,
    }))
    .filter((block) => block.type.length > 0);
}

function normalizeSources(sources: RetrievedSource[]): RetrievedSource[] {
  return sources.map((source) => ({
    ...source,
    id: String(source.id ?? ''),
  }));
}

export async function refreshLiveBlock(subscriptionKey: string): Promise<ContentBlock> {
  const params = new URLSearchParams({ key: subscriptionKey });
  const response = await apiFetch(`/live/blocks/refresh?${params.toString()}`);
  return (await response.json()) as ContentBlock;
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

export type { DemoConfig, DemoChatRequestPayload, DemoChatResponsePayload };

export async function fetchMcpServers(): Promise<McpServerSummary[]> {
  const response = await apiFetch('/mcp/servers');
  if (!response.ok) {
    throw new Error(await response.text());
  }
  const data = (await response.json()) as { servers?: McpServerSummary[] };
  return data.servers ?? [];
}

export async function createMcpServer(payload: {
  name: string;
  url: string;
  enabled?: boolean;
  headers?: Record<string, string>;
}): Promise<McpServerSummary> {
  const response = await apiFetch('/mcp/servers', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return (await response.json()) as McpServerSummary;
}

export async function deleteMcpServer(serverId: string): Promise<void> {
  const response = await apiFetch(`/mcp/servers/${serverId}`, { method: 'DELETE' });
  if (!response.ok) {
    throw new Error(await response.text());
  }
}

export async function testMcpServer(serverId: string): Promise<McpServerTestResult> {
  const response = await apiFetch(`/mcp/servers/${serverId}/test`, { method: 'POST' });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return (await response.json()) as McpServerTestResult;
}

export async function fetchDoctorReport(): Promise<DoctorReport> {
  const response = await apiFetch('/agent/diagnostics');
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return (await response.json()) as DoctorReport;
}

export async function fetchSkills(): Promise<SkillSummary[]> {
  const response = await apiFetch('/agent/skills');
  if (!response.ok) {
    throw new Error(await response.text());
  }
  const data = (await response.json()) as { skills?: SkillSummary[] };
  return data.skills ?? [];
}

export async function fetchAssistants(): Promise<AssistantSummary[]> {
  const response = await apiFetch('/agent/assistants');
  if (!response.ok) {
    throw new Error(await response.text());
  }
  const data = (await response.json()) as { assistants?: AssistantSummary[] };
  return data.assistants ?? [];
}

export async function createAssistant(payload: {
  name: string;
  description?: string;
  instructions?: string;
  allowed_tools?: string[];
  triggers?: string[];
  pick_only?: boolean;
}): Promise<AssistantSummary> {
  const response = await apiFetch('/agent/assistants', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return (await response.json()) as AssistantSummary;
}

export async function updateAssistant(
  assistantId: string,
  payload: {
    enabled?: boolean;
    name?: string;
    description?: string;
    instructions?: string;
    allowed_tools?: string[];
    triggers?: string[];
    pick_only?: boolean;
  },
): Promise<AssistantSummary> {
  const response = await apiFetch(`/agent/assistants/${assistantId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return (await response.json()) as AssistantSummary;
}

export async function deleteAssistant(assistantId: string): Promise<void> {
  const response = await apiFetch(`/agent/assistants/${assistantId}`, { method: 'DELETE' });
  if (!response.ok) {
    throw new Error(await response.text());
  }
}

export async function updateSkill(skillId: string, payload: { enabled?: boolean }): Promise<SkillSummary> {
  const response = await apiFetch(`/agent/skills/${skillId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return (await response.json()) as SkillSummary;
}

export async function fetchAgentTasks(): Promise<AgentTaskSummary[]> {
  const response = await apiFetch('/agent/tasks');
  if (!response.ok) {
    throw new Error(await response.text());
  }
  const data = (await response.json()) as { tasks?: AgentTaskSummary[] };
  return data.tasks ?? [];
}

export async function updateAgentTaskStatus(
  taskId: string,
  status: AgentTaskSummary['status'],
): Promise<AgentTaskSummary> {
  const response = await apiFetch(`/agent/tasks/${taskId}`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return (await response.json()) as AgentTaskSummary;
}

export async function deleteAgentTask(taskId: string): Promise<void> {
  const response = await apiFetch(`/agent/tasks/${taskId}`, { method: 'DELETE' });
  if (!response.ok) {
    throw new Error(await response.text());
  }
}

export async function fetchDemoConfig(): Promise<DemoConfig> {
  const response = await safeFetch(`${getBaseUrl()}/demo/config`, { method: 'GET' });
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || 'Demo is not available');
  }
  return (await response.json()) as DemoConfig;
}

export async function sendDemoMessage(
  payload: DemoChatRequestPayload,
  onStatus?: (message: string) => void,
): Promise<DemoChatResponsePayload> {
  const response = await safeFetch(`${getBaseUrl()}/demo/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || response.statusText);
  }

  if (response.headers.get('content-type')?.includes('text/event-stream')) {
    let finalResponse: DemoChatResponsePayload | null = null;
    let streamErrorPayload: string | null = null;

    await streamSseEvents(response, (event) => {
      if (event.type === 'status' && typeof event.message === 'string') {
        onStatus?.(event.message);
        return;
      }
      if (event.type === 'final' && event.response) {
        finalResponse = event.response as DemoChatResponsePayload;
        return;
      }
      if (event.type === 'error') {
        const detail = (event as { detail?: { message?: string }; message?: string }).detail;
        if (detail && typeof detail === 'object') {
          streamErrorPayload = JSON.stringify({ detail });
        } else if (typeof event.message === 'string') {
          streamErrorPayload = JSON.stringify({ detail: event.message });
        } else {
          streamErrorPayload = JSON.stringify({ detail: 'Demo chat failed' });
        }
      }
    });

    if (streamErrorPayload) {
      throw new Error(streamErrorPayload);
    }
    if (!finalResponse) {
      throw new Error('Demo stream completed without a final response');
    }
    return finalResponse;
  }

  return (await response.json()) as DemoChatResponsePayload;
}
