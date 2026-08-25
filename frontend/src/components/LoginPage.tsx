import { GoogleLogin } from '@react-oauth/google';
import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { AuthConfig } from '../api';
import { exchangeGoogleToken } from '../api';
import { consumeSessionNotice } from '../auth';
import { shouldUseNativeGoogleSignIn, signInWithGoogle } from '../auth/googleSignIn';
import { queryKeys } from '../query/keys';
import { friendlyLoginError } from '../utils/loginErrors';
import { CuraiLogo } from './CuraiLogo';

interface Props {
  authConfig: AuthConfig;
  onAuthenticated?: () => void;
  /** Admin portal uses tighter copy about allowlisted accounts. */
  variant?: 'app' | 'admin';
}

export function LoginPage({ authConfig, onAuthenticated, variant = 'app' }: Props) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [sessionNotice] = useState<string | null>(() => consumeSessionNotice());
  const [isSubmitting, setIsSubmitting] = useState(false);
  const googleButtonRef = useRef<HTMLDivElement>(null);
  const [googleButtonWidth, setGoogleButtonWidth] = useState(280);
  const useNativeGoogle = shouldUseNativeGoogleSignIn();
  const isAdmin = variant === 'admin';
  const privacyUrl = authConfig.privacy_policy_url || '/privacy';
  const termsUrl = authConfig.terms_of_service_url || '/terms';
  const supportEmail = authConfig.support_email || 'hello@cura-i.com';

  useEffect(() => {
    if (useNativeGoogle) {
      return undefined;
    }

    const container = googleButtonRef.current;
    if (!container) {
      return undefined;
    }

    const updateWidth = () => {
      const width = Math.min(400, Math.max(200, Math.floor(container.clientWidth)));
      setGoogleButtonWidth(width);
    };

    updateWidth();
    const observer = new ResizeObserver(updateWidth);
    observer.observe(container);
    return () => observer.disconnect();
  }, [useNativeGoogle]);

  const handleGoogleSuccess = async (credential?: string) => {
    if (!credential) {
      setError('Google did not return a sign-in credential.');
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      await exchangeGoogleToken(credential);
      await queryClient.invalidateQueries({ queryKey: queryKeys.currentUser });
      onAuthenticated?.();
    } catch (submitError) {
      const message = submitError instanceof Error ? submitError.message : 'Sign-in failed';
      setError(friendlyLoginError(message));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleNativeGoogleSignIn = async () => {
    const clientId = authConfig.google_client_id;
    if (!clientId) {
      setError('Google sign-in is not configured.');
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      const { idToken } = await signInWithGoogle(clientId);
      await handleGoogleSuccess(idToken);
    } catch (submitError) {
      const message = submitError instanceof Error ? submitError.message : 'Sign-in failed';
      setError(friendlyLoginError(message));
      setIsSubmitting(false);
    }
  };

  return (
    <main
      className="classic-font flex min-h-[100dvh] items-center justify-center bg-[var(--ui-bg)] px-4 py-10 text-[var(--phosphor)]"
      style={{
        paddingTop: 'max(2.5rem, var(--safe-area-top))',
        paddingBottom: 'max(2.5rem, var(--safe-area-bottom))',
      }}
    >
      <div className="elevated-panel w-full max-w-md rounded-2xl border border-[var(--ui-border)] p-6 shadow-xl sm:p-8">
        <div className="mb-6 flex flex-col items-center text-center">
          <CuraiLogo state={isSubmitting ? 'thinking' : error ? 'error' : 'idle'} size={48} className="mb-4" />
          <h1 className="font-display text-2xl font-semibold tracking-tight text-[var(--phosphor-bright)]">
            {isAdmin ? 'CurieAI Admin' : 'CurieAI'}
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-[var(--phosphor-dim)]">
            {isAdmin
              ? 'Sign in with an allowlisted Google account to manage providers, users, and usage.'
              : 'Sign in to access your conversations, documents, and smart-routed chat history.'}
          </p>
        </div>

        {sessionNotice && !error && (
          <div className="mb-4 rounded-xl border border-[color-mix(in_srgb,var(--ui-accent)_35%,transparent)] bg-[color-mix(in_srgb,var(--ui-accent)_12%,transparent)] px-4 py-3 text-sm text-[var(--phosphor-bright)]">
            {sessionNotice}
          </div>
        )}

        {authConfig.google_auth_enabled ? (
          <div className="flex w-full flex-col items-center gap-3">
            {useNativeGoogle ? (
              <button
                type="button"
                onClick={() => {
                  void handleNativeGoogleSignIn();
                }}
                disabled={isSubmitting}
                className="touch-target w-full rounded-full border border-[var(--ui-border-strong)] bg-[var(--ui-panel)] px-4 py-3 text-sm font-medium text-[var(--phosphor-bright)] transition hover:bg-[var(--ui-bg-elevated)] disabled:cursor-not-allowed disabled:opacity-60"
              >
                Continue with Google
              </button>
            ) : (
              <div ref={googleButtonRef} className={`w-full ${isSubmitting ? 'pointer-events-none opacity-60' : ''}`}>
                <GoogleLogin
                  onSuccess={(response) => {
                    void handleGoogleSuccess(response.credential);
                  }}
                  onError={() => {
                    setError('Google sign-in was cancelled or failed.');
                  }}
                  useOneTap={false}
                  theme="outline"
                  size="large"
                  text="continue_with"
                  shape="pill"
                  width={String(googleButtonWidth)}
                />
              </div>
            )}
            {isSubmitting && (
              <p className="text-xs text-[var(--phosphor-dim)]">Completing sign-in…</p>
            )}
          </div>
        ) : authConfig.auth_disabled ? (
          <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
            Auth is disabled on this server (<code className="rounded bg-black/20 px-1 py-0.5 text-xs">AUTH_DISABLED=true</code>
            ). Set <code className="rounded bg-black/20 px-1 py-0.5 text-xs">AUTH_DISABLED=false</code> and{' '}
            <code className="rounded bg-black/20 px-1 py-0.5 text-xs">ADMIN_EMAILS</code> to require Google login for admin.
          </div>
        ) : (
          <div className="rounded-xl border border-[color-mix(in_srgb,var(--ui-accent)_30%,transparent)] bg-[color-mix(in_srgb,var(--ui-accent)_10%,transparent)] px-4 py-3 text-sm text-[var(--phosphor)]">
            Authentication is enabled but Google Sign-In is not configured. Set{' '}
            <code className="rounded bg-black/20 px-1 py-0.5 text-xs">GOOGLE_CLIENT_ID</code> on the server.
          </div>
        )}

        {error && (
          <div className="mt-4 rounded-xl border border-[rgba(239,68,68,0.35)] bg-[rgba(239,68,68,0.1)] px-4 py-3 text-sm text-[#f87171]">
            {error}
          </div>
        )}

        <p className="mt-6 text-center text-xs leading-relaxed text-[var(--phosphor-dim)]">
          {isAdmin
            ? 'Only emails listed in ADMIN_EMAILS (or invited as staff) can open this portal.'
            : 'Your conversations are private and tied to your account.'}
          {' '}
          <a
            className="underline decoration-[var(--ui-border)] underline-offset-2 hover:text-[var(--phosphor)]"
            href={privacyUrl}
          >
            Privacy
          </a>
          {' · '}
          <a
            className="underline decoration-[var(--ui-border)] underline-offset-2 hover:text-[var(--phosphor)]"
            href={termsUrl}
          >
            Terms
          </a>
          {' · '}
          <a
            className="underline decoration-[var(--ui-border)] underline-offset-2 hover:text-[var(--phosphor)]"
            href={`mailto:${supportEmail}`}
          >
            {supportEmail}
          </a>
        </p>
      </div>
    </main>
  );
}
