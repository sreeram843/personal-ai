export type Role = 'user' | 'assistant' | 'system';

export interface ChatMessage {
  id: string;
  role: Role;
  content: string;
  createdAt: number;
  latencyMs?: number;
  sources?: RetrievedSource[];
  workflow?: WorkflowTrace;
  workflowMemoryEvents?: WorkflowMemoryEvent[];
  workflowSourceEvents?: WorkflowSourceEvent[];
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

export interface RequestMessage {
  role: Role;
  content: string;
}

export interface RagChatRequestPayload {
  message: string;
}

export interface ChatResponsePayload {
  message: string;
  sources?: RetrievedSource[];
  workflow?: WorkflowTrace;
}

export interface WorkflowEventPayload {
  type: 'workflow' | 'final' | 'error' | 'memory' | 'sources';
  workflow?: WorkflowTrace;
  response?: ChatResponsePayload;
  message?: string;
  phase?: 'read' | 'write';
  summary?: string;
  conversation_id?: string;
  step_id?: string;
  agent?: string;
  sources?: RetrievedSource[];
}

export interface WorkflowMemoryEvent {
  phase: 'read' | 'write';
  summary: string;
}

export interface WorkflowSourceEvent {
  stepId: string;
  agent: string;
  count: number;
}

export interface WorkflowStep {
  id: string;
  agent: string;
  title: string;
  status: 'planned' | 'in_progress' | 'completed' | 'failed' | 'skipped';
  summary?: string;
  depends_on?: string[];
}

export interface WorkflowTrace {
  mode: 'multi_agent';
  status: 'completed' | 'failed' | 'partial';
  steps: WorkflowStep[];
}

export interface UploadStatus {
  id: string;
  name: string;
  status: 'idle' | 'uploading' | 'success' | 'error';
  error?: string;
}

export type ConversationMode = 'chat' | 'smart';

export type PersonaType = 'ideal_chatbot' | 'therapist' | 'barney';

export interface Persona {
  name: PersonaType;
  description: string;
}
