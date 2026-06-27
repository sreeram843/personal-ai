import { describe, expect, it } from 'vitest';
import { buildChatRequestMessages } from './api';
import type { ChatMessage } from './types';

describe('buildChatRequestMessages', () => {
  it('drops optimistic empty assistant placeholders', () => {
    const history: ChatMessage[] = [
      { id: '1', role: 'user', content: 'Best bbq in Austin?', createdAt: 1 },
      { id: '2', role: 'assistant', content: '', createdAt: 2 },
    ];

    expect(buildChatRequestMessages(history, 'Best bbq in Austin?')).toEqual([
      { role: 'user', content: 'Best bbq in Austin?' },
    ]);
  });

  it('does not duplicate the latest user turn', () => {
    const history: ChatMessage[] = [
      { id: '1', role: 'user', content: 'Hello', createdAt: 1 },
      { id: '2', role: 'assistant', content: 'Hi there', createdAt: 2 },
      { id: '3', role: 'user', content: 'Follow up', createdAt: 3 },
      { id: '4', role: 'assistant', content: '', createdAt: 4 },
    ];

    expect(buildChatRequestMessages(history, 'Follow up')).toEqual([
      { role: 'user', content: 'Hello' },
      { role: 'assistant', content: 'Hi there' },
      { role: 'user', content: 'Follow up' },
    ]);
  });
});
