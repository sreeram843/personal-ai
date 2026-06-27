import { describe, expect, it } from 'vitest';
import {
  classifyChatError,
  createChatRequestError,
  errorHeadline,
  isAbortError,
} from './chatErrors';

describe('chatErrors', () => {
  it('classifies HTTP 429 as rate_limit', () => {
    const error = createChatRequestError(429, '{"detail":"Rate limit exceeded"}');
    expect(error.kind).toBe('rate_limit');
    expect(classifyChatError(error).kind).toBe('rate_limit');
  });

  it('classifies policy refusals', () => {
    const error = createChatRequestError(400, '{"detail":"Request violates content policy"}');
    expect(error.kind).toBe('refused');
    expect(errorHeadline(error.kind)).toBe('Request declined');
  });

  it('detects abort errors', () => {
    expect(isAbortError(new DOMException('Aborted', 'AbortError'))).toBe(true);
    expect(isAbortError(new Error('Fetch is aborted'))).toBe(true);
  });
});
