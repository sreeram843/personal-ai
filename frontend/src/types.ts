import type { ContentBlock } from './types/liveData';

export type ToolPermissionMode = 'auto' | 'ask' | 'plan';

export interface PlannedToolCall {
  tool_id: string;
  name: string;
  reason: string;
  inputs_preview?: Record<string, unknown>;
}

export interface PendingToolApproval {
  tool_id: string;
  name: string;
  description: string;
  risk_class: string;
  inputs_preview?: Record<string, unknown>;
}

export interface AgentSettings {
  toolPermissionMode: ToolPermissionMode;
}

export interface McpServerSummary {
  id: string;
  name: string;
  url: string;
  enabled: boolean;
  header_keys: string[];
  last_status?: string | null;
  last_error?: string | null;
  tool_count?: number;
  last_checked_at?: string | null;
}

export interface McpServerTestResult {
  ok: boolean;
  tool_count?: number;
  tools?: string[];
  error?: string | null;
}

export interface DoctorReport {
  status: string;
  issues: string[];
  features: Record<string, unknown>;
  checks: Record<string, unknown>;
}

export interface SkillSummary {
  id: string;
  name: string;
  description?: string;
  triggers: string[];
  allowed_tools: string[];
  enabled: boolean;
  bundled: boolean;
  pick_only?: boolean;
}

export interface AssistantSummary {
  id: string;
  name: string;
  description?: string;
  instructions?: string;
  triggers: string[];
  allowed_tools: string[];
  enabled: boolean;
  bundled: boolean;
  pick_only: boolean;
  is_default: boolean;
}

export interface AgentTaskSummary {
  id: string;
  title: string;
  detail: string;
  status: 'pending' | 'in_progress' | 'completed' | 'cancelled';
  source: 'planned_tool' | 'user' | 'skill';
  tool_id?: string | null;
  conversation_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgentSendOptions {
  toolPermissionMode?: ToolPermissionMode;
  approvedToolIds?: string[];
}

export type ConversationMode = 'chat' | 'smart';

export type Role = 'user' | 'assistant' | 'system';

export type ChatErrorKind = 'network' | 'timeout' | 'rate_limit' | 'refused' | 'unknown';

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
  reasoning?: string;
  sentiment?: string;
  inputTokens?: number;
  outputTokens?: number;
  errorKind?: ChatErrorKind;
  errorDetail?: string;
  blocks?: ContentBlock[];
  plannedTools?: PlannedToolCall[];
  pendingToolApprovals?: PendingToolApproval[];
  toolPermissionMode?: ToolPermissionMode;
  showLiveSkeleton?: boolean;
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
  conversation_id?: string;
  latency_ms?: number;
  reasoning?: string;
  sentiment?: string;
  prompt_tokens?: number;
  completion_tokens?: number;
  blocks?: ContentBlock[];
  planned_tools?: PlannedToolCall[];
  pending_tool_approvals?: PendingToolApproval[];
  tool_permission_mode?: ToolPermissionMode;
}

export interface WorkflowEventPayload {
  type: 'workflow' | 'final' | 'error' | 'memory' | 'sources' | 'conversation' | 'block' | 'status';
  workflow?: WorkflowTrace;
  response?: ChatResponsePayload;
  message?: string;
  block?: ContentBlock;
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
  status: 'idle' | 'uploading' | 'queued' | 'processing' | 'success' | 'error';
  error?: string;
  file?: File;
}

export interface DemoConfig {
  enabled: boolean;
  max_questions: number;
  intro: string;
  full_app_url?: string | null;
  suggested_prompts?: string[];
}

export interface DemoChatRequestPayload {
  session_id: string;
  message: string;
  messages: Array<{ role: Role; content: string }>;
}

export interface DemoChatResponsePayload extends ChatResponsePayload {
  questions_used: number;
  questions_remaining: number;
  limit_reached: boolean;
  full_app_url?: string | null;
}
