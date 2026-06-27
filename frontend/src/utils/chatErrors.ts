import type { ChatErrorKind } from '../types';

const REFUSED_MARKERS = [
  'content policy',
  'safety',
  'refused',
  'declined',
  'not allowed',
  'cannot assist',
  "can't assist",
  'harmful',
  'violat',
];

export class ChatRequestError extends Error {
  readonly kind: ChatErrorKind;

  readonly status?: number;

  constructor(kind: ChatErrorKind, message: string, status?: number) {
    super(message);
    this.name = 'ChatRequestError';
    this.kind = kind;
    this.status = status;
  }
}

function parseErrorDetail(raw: string): string {
  const trimmed = raw.trim();
  if (!trimmed) {
    return 'Unknown error';
  }
  try {
    const parsed = JSON.parse(trimmed) as { detail?: string | Array<{ msg?: string }> };
    if (typeof parsed.detail === 'string') {
      return parsed.detail;
    }
    if (Array.isArray(parsed.detail)) {
      const parts = parsed.detail
        .map((item) => (typeof item?.msg === 'string' ? item.msg : ''))
        .filter(Boolean);
      if (parts.length > 0) {
        return parts.join(' ');
      }
    }
  } catch {
    // keep raw text
  }
  return trimmed;
}

function classifyDetail(detail: string, status?: number): ChatErrorKind {
  const lowered = detail.toLowerCase();

  if (status === 429 || lowered.includes('rate limit') || lowered.includes('too many requests')) {
    return 'rate_limit';
  }
  if (
    status === 408 ||
    status === 504 ||
    lowered.includes('timeout') ||
    lowered.includes('timed out')
  ) {
    return 'timeout';
  }
  if (
    lowered.includes('tool_use_failed') ||
    lowered.includes('tool choice is none') ||
    lowered.includes('without a final response') ||
    lowered.includes('openai-compatible provider request failed')
  ) {
    return 'unknown';
  }
  if (
    status === 502 ||
    status === 503 ||
    lowered.includes('network') ||
    lowered.includes('connection') ||
    lowered.includes('unavailable') ||
    lowered.includes('failed to fetch') ||
    lowered.includes('load failed')
  ) {
    return 'network';
  }
  if (
    status === 400 ||
    status === 403 ||
    REFUSED_MARKERS.some((marker) => lowered.includes(marker))
  ) {
    return 'refused';
  }
  return 'unknown';
}

export function createChatRequestError(status: number, rawDetail: string): ChatRequestError {
  const detail = parseErrorDetail(rawDetail);
  const kind = classifyDetail(detail, status);
  return new ChatRequestError(kind, detail, status);
}

export function classifyChatError(error: unknown): { kind: ChatErrorKind; detail: string } {
  if (error instanceof ChatRequestError) {
    return { kind: error.kind, detail: error.message };
  }

  if (error instanceof DOMException && error.name === 'AbortError') {
    return { kind: 'unknown', detail: 'Request aborted' };
  }

  const message = error instanceof Error ? error.message : 'Unknown error';
  const detail = parseErrorDetail(message);

  if (/aborted/i.test(detail)) {
    return { kind: 'unknown', detail };
  }

  return { kind: classifyDetail(detail), detail };
}

export function isAbortError(error: unknown): boolean {
  if (error instanceof DOMException && error.name === 'AbortError') {
    return true;
  }
  if (error instanceof Error && /aborted/i.test(error.message)) {
    return true;
  }
  return false;
}

export function isLegacyErrorContent(content: string): boolean {
  return content.trimStart().startsWith('⚠️');
}

export function resolveMessageError(message: {
  content: string;
  errorKind?: ChatErrorKind;
  errorDetail?: string;
}): { kind: ChatErrorKind; detail: string } | null {
  if (message.errorKind) {
    return {
      kind: message.errorKind,
      detail: message.errorDetail ?? message.content,
    };
  }
  if (isLegacyErrorContent(message.content)) {
    const detail = message.content.replace(/^⚠️\s*/, '').replace(/^Unable to retrieve response\.\s*/i, '').trim();
    return { kind: classifyDetail(detail), detail: detail || message.content };
  }
  return null;
}

export function errorHeadline(kind: ChatErrorKind): string {
  switch (kind) {
    case 'network':
      return 'Connection failed';
    case 'timeout':
      return 'Request timed out';
    case 'rate_limit':
      return 'Rate limited';
    case 'refused':
      return 'Request declined';
    default:
      return 'Something went wrong';
  }
}

export function errorDescription(kind: ChatErrorKind, detail: string): string {
  switch (kind) {
    case 'network':
      return 'Could not reach the server. Check your connection and try again.';
    case 'timeout':
      return 'The request took too long. Try again or shorten your prompt.';
    case 'rate_limit':
      return 'Too many requests right now. Wait a moment and try again.';
    case 'refused':
      return detail || 'The model declined this request. Try editing your message.';
    default:
      return detail || 'Unable to retrieve a response.';
  }
}
