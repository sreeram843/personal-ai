/** Classify demo chat failures: quota vs provider rate-limit vs other. */

export function parseDemoError(error: unknown): string {
  if (!(error instanceof Error)) {
    return 'Something went wrong. Please try again.';
  }
  const raw = error.message.trim();
  if (!raw) {
    return 'Something went wrong. Please try again.';
  }
  try {
    const parsed = JSON.parse(raw) as {
      detail?: string | { message?: string; code?: string; limit_reached?: boolean };
    };
    if (typeof parsed.detail === 'string') {
      return parsed.detail;
    }
    if (parsed.detail && typeof parsed.detail === 'object' && parsed.detail.message) {
      return parsed.detail.message;
    }
  } catch {
    // keep raw text
  }
  return raw;
}

export function isDemoQuotaError(message: string, error: unknown): boolean {
  if (error instanceof Error) {
    try {
      const parsed = JSON.parse(error.message) as {
        detail?: { limit_reached?: boolean; message?: string };
      };
      if (parsed.detail && typeof parsed.detail === 'object' && parsed.detail.limit_reached === true) {
        return true;
      }
    } catch {
      // fall through to message checks
    }
  }
  return message.toLowerCase().includes('demo question limit reached');
}

export function isProviderRateLimitError(message: string, error: unknown): boolean {
  if (error instanceof Error) {
    try {
      const parsed = JSON.parse(error.message) as { detail?: { code?: string } };
      if (
        parsed.detail &&
        typeof parsed.detail === 'object' &&
        parsed.detail.code === 'provider_rate_limit'
      ) {
        return true;
      }
    } catch {
      // fall through
    }
  }
  const lowered = message.toLowerCase();
  return (
    lowered.includes('rate_limit') ||
    lowered.includes('rate limit') ||
    lowered.includes('tokens per minute') ||
    lowered.includes('provider_rate_limit') ||
    lowered.includes('(429)')
  );
}

export function friendlyDemoError(
  message: string,
  error: unknown,
): { text: string; quotaExhausted: boolean } {
  if (isDemoQuotaError(message, error)) {
    return {
      text: 'Demo question limit reached. Sign in for unlimited conversations.',
      quotaExhausted: true,
    };
  }
  if (isProviderRateLimitError(message, error)) {
    return {
      text: 'The demo is temporarily rate-limited. Please wait a few seconds and try again.',
      quotaExhausted: false,
    };
  }
  return { text: message, quotaExhausted: false };
}
