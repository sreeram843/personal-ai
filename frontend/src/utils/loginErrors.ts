/** Map Google / auth API failures to actionable login copy. */
export function friendlyLoginError(raw: string): string {
  const text = raw.trim();
  const lowered = text.toLowerCase();

  if (lowered.includes('origin_mismatch') || lowered.includes('origin is not allowed')) {
    return 'This site origin is not allowed for Google Sign-In. Add the exact URL (scheme + host) under Google Cloud → Credentials → Authorized JavaScript origins.';
  }
  if (
    lowered.includes('access_denied') ||
    lowered.includes('has not completed the google verification') ||
    lowered.includes('app is currently being tested') ||
    lowered.includes('test user')
  ) {
    return 'Google blocked sign-in for this account. Publish the OAuth consent screen, or add this email as a Test user while the app is in Testing.';
  }
  if (lowered.includes('invite') || lowered.includes('not invited') || lowered.includes('signup')) {
    return 'Your Google account is not invited yet. Ask an admin for an invite, or have them add your email to ADMIN_EMAILS.';
  }
  if (lowered.includes('account is disabled')) {
    return 'This account has been disabled. Contact support if you need access restored.';
  }
  if (lowered.includes('google sign-in is not configured') || lowered.includes('503')) {
    return 'Google Sign-In is not configured on the server. Set GOOGLE_CLIENT_ID and AUTH_DISABLED=false, then redeploy.';
  }
  if (lowered.includes('auth_disabled') || lowered.includes('while auth_disabled')) {
    return 'Google Sign-In is disabled while AUTH_DISABLED=true on the server.';
  }

  try {
    const parsed = JSON.parse(text) as { detail?: string };
    if (typeof parsed.detail === 'string' && parsed.detail.trim()) {
      return friendlyLoginError(parsed.detail);
    }
  } catch {
    // keep raw
  }

  return text || 'Sign-in failed';
}
