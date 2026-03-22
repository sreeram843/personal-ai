export type Role = 'user' | 'assistant' | 'system';

export interface ChatMessage {
  id: string;
  role: Role;
  content: string;
  createdAt: number;
  latencyMs?: number;
  sources?: RetrievedSource[];
}

export interface RetrievedSource {
  id: string;
  score?: number;
  text?: string;
  metadata?: Record<string, unknown>;
}

export interface ChatRequestPayload {
  message: string;
}

export interface RagChatRequestPayload {
  message: string;
}

export interface ChatResponsePayload {
  message: string;
  sources?: RetrievedSource[];
}

export interface UploadStatus {
  id: string;
  name: string;
  status: 'idle' | 'uploading' | 'success' | 'error';
  error?: string;
}

export type ConversationMode = 'chat' | 'rag';
