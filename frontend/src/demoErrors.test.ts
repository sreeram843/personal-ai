import { describe, expect, it } from 'vitest';
import { friendlyDemoError } from './demoErrors';

describe('friendlyDemoError', () => {
  it('does not treat Groq TPM rate limits as demo quota exhaustion', () => {
    const message =
      'Demo chat failed: OpenAI-compatible provider request failed (429): Rate limit reached for model llama-3.1-8b-instant';
    const result = friendlyDemoError(message, new Error(message));
    expect(result.quotaExhausted).toBe(false);
    expect(result.text.toLowerCase()).toContain('rate-limited');
    expect(result.text.toLowerCase()).not.toContain('sign in');
  });

  it('treats structured demo quota errors as exhausted', () => {
    const error = new Error(
      JSON.stringify({
        detail: {
          message: 'Demo question limit reached.',
          limit_reached: true,
          questions_remaining: 0,
        },
      }),
    );
    const result = friendlyDemoError('Demo question limit reached.', error);
    expect(result.quotaExhausted).toBe(true);
    expect(result.text.toLowerCase()).toContain('sign in');
  });

  it('uses provider_rate_limit code from structured SSE errors', () => {
    const error = new Error(
      JSON.stringify({
        detail: {
          message: 'The demo is temporarily rate-limited. Please wait a few seconds and try again.',
          code: 'provider_rate_limit',
          limit_reached: false,
        },
      }),
    );
    const result = friendlyDemoError('ignored', error);
    expect(result.quotaExhausted).toBe(false);
    expect(result.text.toLowerCase()).toContain('rate-limited');
  });
});
