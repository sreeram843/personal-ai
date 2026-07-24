const AUTH_TOKEN_KEY = 'personal-ai-auth-token';
const SESSION_NOTICE_KEY = 'personal-ai-session-notice';
export const AUTH_CHANGED_EVENT = 'personal-ai-auth-changed';

export const SESSION_EXPIRED_MESSAGE = 'Session expired — sign in again';

function notifyAuthChanged(): void {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event(AUTH_CHANGED_EVENT));
  }
}

export function getAuthToken(): string | null {
  if (typeof window === 'undefined') {
    return null;
  }
  return window.localStorage.getItem(AUTH_TOKEN_KEY);
}

export function setAuthToken(token: string): void {
  if (typeof window === 'undefined') {
    return;
  }
  window.localStorage.setItem(AUTH_TOKEN_KEY, token);
  clearSessionNotice();
  notifyAuthChanged();
}

export function clearAuthToken(): void {
  if (typeof window === 'undefined') {
    return;
  }
  window.localStorage.removeItem(AUTH_TOKEN_KEY);
  notifyAuthChanged();
}

/** Clear token after an unauthorized API response and surface a login banner. */
export function expireAuthSession(): void {
  if (typeof window === 'undefined') {
    return;
  }
  window.sessionStorage.setItem(SESSION_NOTICE_KEY, SESSION_EXPIRED_MESSAGE);
  clearAuthToken();
}

export function consumeSessionNotice(): string | null {
  if (typeof window === 'undefined') {
    return null;
  }
  const notice = window.sessionStorage.getItem(SESSION_NOTICE_KEY);
  if (notice) {
    window.sessionStorage.removeItem(SESSION_NOTICE_KEY);
  }
  return notice;
}

export function clearSessionNotice(): void {
  if (typeof window === 'undefined') {
    return;
  }
  window.sessionStorage.removeItem(SESSION_NOTICE_KEY);
}

export function authHeaders(): Record<string, string> {
  const token = getAuthToken();
  if (!token) {
    return {};
  }
  return { Authorization: `Bearer ${token}` };
}
