import type {
  ChatResponsePayload,
  ConversationMode,
  PersonaInfoPayload,
  PersonaListPayload,
  PersonaPreviewPayload,
  RetrievedSource,
} from './types';

const BASE_URL = 'http://localhost:8000';

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

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ message }),
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

  const response = await fetch(`${BASE_URL}/ingest`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || response.statusText);
  }
}

async function requestJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, init);
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || response.statusText);
  }
  return (await response.json()) as T;
}

export async function getActivePersona(): Promise<string> {
  const data = await requestJSON<PersonaInfoPayload>('/persona/active');
  return data.persona;
}

export async function switchPersona(name: string): Promise<string> {
  const data = await requestJSON<PersonaInfoPayload>('/persona/switch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  return data.persona;
}

export async function getPersonaPreview(): Promise<PersonaPreviewPayload> {
  return requestJSON<PersonaPreviewPayload>('/persona/preview');
}

export async function getPersonaList(): Promise<string[]> {
  const data = await requestJSON<PersonaListPayload>('/persona/list');
  return data.personas;
}
