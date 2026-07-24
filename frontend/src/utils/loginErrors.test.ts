import { describe, expect, it } from 'vitest';
import { friendlyLoginError } from './loginErrors';

describe('friendlyLoginError', () => {
  it('explains origin mismatch', () => {
    expect(friendlyLoginError('Error 400: origin_mismatch')).toMatch(/Authorized JavaScript origins/i);
  });

  it('explains testing-mode / test user blocks', () => {
    expect(friendlyLoginError('Access blocked: app is currently being tested')).toMatch(/Test user|Publish/i);
  });

  it('unwraps FastAPI detail JSON', () => {
    expect(friendlyLoginError(JSON.stringify({ detail: 'Account is disabled' }))).toMatch(/disabled/i);
  });
});
