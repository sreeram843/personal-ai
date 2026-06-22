import type { ChatMessage } from '../types';

export type CuraiLogoState = 'idle' | 'thinking' | 'active' | 'error';

export function resolveCuraiLogoState(options: {
  isLoading: boolean;
  hasBootstrapError: boolean;
  messages: ChatMessage[];
}): CuraiLogoState {
  if (options.hasBootstrapError) {
    return 'error';
  }

  if (options.isLoading) {
    const streamingAssistant = [...options.messages].reverse().find((message) => message.role === 'assistant');
    const content = streamingAssistant?.content?.trim() ?? '';
    const hasStreamingContent =
      content.length > 0 && content !== 'Coordinating workflow...' && !content.startsWith('⚠️');
    return hasStreamingContent ? 'active' : 'thinking';
  }

  const lastMessage = options.messages[options.messages.length - 1];
  if (lastMessage?.role === 'assistant' && lastMessage.content.startsWith('⚠️')) {
    return 'error';
  }

  return 'idle';
}

export function resolveAssistantLogoState(message: ChatMessage, isStreaming: boolean): CuraiLogoState {
  if (message.content.startsWith('⚠️')) {
    return 'error';
  }
  if (!isStreaming) {
    return 'idle';
  }
  const content = message.content.trim();
  if (content.length > 0 && content !== 'Coordinating workflow...') {
    return 'active';
  }
  return 'thinking';
}

export const curaiLogoStateLabels: Record<CuraiLogoState, string> = {
  idle: 'Assistant',
  thinking: 'Thinking',
  active: 'Responding',
  error: 'Unavailable',
};
