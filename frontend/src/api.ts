import type {
  ChatMessage,
  ChatResponsePayload,
  ConversationMode,
  PersonaType,
  RetrievedSource,
  WorkflowEventPayload,
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
  conversationId: string,
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
          conversation_id: conversationId,
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
          conversation_id: conversationId,
          messages,
        };

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

export async function switchPersona(persona: PersonaType): Promise<{ status: string; active: PersonaType }> {
  const response = await safeFetch(`${BASE_URL}/personas/switch`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ persona }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || response.statusText);
  }

  return response.json();
}


