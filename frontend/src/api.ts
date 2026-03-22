import type {
  ChatResponsePayload,
  ConversationMode,
  RetrievedSource,
} from './types';

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

  // If app is opened from a remote host (ngrok/domain/phone), avoid broken localhost API targets.
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

    // Safari/mobile fallback: retry using same-origin endpoint if configured base URL fails.
    const pathname = new URL(input).pathname;
    return fetch(pathname, init);
  }
}

async function streamResponse(response: Response, onChunk: (chunk: string) => void) {
  if (!response.body) {
    return '';
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let result = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    const chunk = decoder.decode(value, { stream: true });
    result += chunk;
    onChunk(chunk);
  }

  return result;
}

export async function sendMessage(
  mode: ConversationMode,
  message: string,
  signal: AbortSignal,
  onStreamChunk?: (chunk: string) => void,
): Promise<ChatResponsePayload> {
  const endpoint = mode === 'rag' ? '/rag_chat' : '/chat';
  const url = `${BASE_URL}${endpoint}`;

  const bodyPayload: Record<string, unknown> = { message };

  const response = await safeFetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(bodyPayload),
    signal,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || response.statusText);
  }

  if (response.headers.get('content-type')?.includes('text/event-stream')) {
    let aggregated = '';
    await streamResponse(response, (chunk) => {
      aggregated += chunk;
      onStreamChunk?.(chunk);
    });
    return { message: aggregated };
  }

  if (response.headers.get('content-type')?.includes('application/json')) {
    const data = (await response.json()) as ChatResponsePayload;
    if (data.sources && mode === 'rag') {
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

export async function uploadDocuments(files: File[]): Promise<void> {
  const formData = new FormData();
  files.forEach((file) => {
    formData.append('files', file);
  });

  const response = await safeFetch(`${BASE_URL}/ingest`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || response.statusText);
  }
}


