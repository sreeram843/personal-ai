import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  SESSION_EXPIRED_MESSAGE,
  clearSessionNotice,
  consumeSessionNotice,
  expireAuthSession,
  getAuthToken,
  setAuthToken,
} from './auth';

function createMemoryStorage(): Storage {
  const store = new Map<string, string>();
  return {
    get length() {
      return store.size;
    },
    clear: () => store.clear(),
    getItem: (key: string) => (store.has(key) ? store.get(key)! : null),
    key: (index: number) => Array.from(store.keys())[index] ?? null,
    removeItem: (key: string) => {
      store.delete(key);
    },
    setItem: (key: string, value: string) => {
      store.set(key, String(value));
    },
  };
}

describe('auth session notices', () => {
  beforeEach(() => {
    vi.stubGlobal('window', {
      localStorage: createMemoryStorage(),
      sessionStorage: createMemoryStorage(),
      dispatchEvent: () => true,
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('stores a session-expired notice when the session expires', () => {
    setAuthToken('test-token');
    expireAuthSession();

    expect(getAuthToken()).toBeNull();
    expect(consumeSessionNotice()).toBe(SESSION_EXPIRED_MESSAGE);
    expect(consumeSessionNotice()).toBeNull();
  });

  it('clears the notice when a new token is saved', () => {
    expireAuthSession();
    setAuthToken('fresh-token');
    expect(consumeSessionNotice()).toBeNull();
    clearSessionNotice();
  });
});
