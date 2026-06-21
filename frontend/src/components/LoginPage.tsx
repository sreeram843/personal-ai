import { GoogleLogin } from '@react-oauth/google';
import { Sparkles } from 'lucide-react';
import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { AuthConfig } from '../api';
import { exchangeGoogleToken } from '../api';
import { queryKeys } from '../query/keys';

interface Props {
  authConfig: AuthConfig;
  onAuthenticated?: () => void;
}

export function LoginPage({ authConfig, onAuthenticated }: Props) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

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
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="classic-font flex min-h-screen items-center justify-center bg-[var(--ui-bg)] px-4 py-10 text-[var(--phosphor)]">
      <div className="elevated-panel w-full max-w-md rounded-2xl border border-[var(--ui-border)] p-6 shadow-xl sm:p-8">
        <div className="mb-6 flex flex-col items-center text-center">
          <div className="mb-4 grid h-12 w-12 place-content-center rounded-xl bg-[var(--ui-focus)] text-[var(--ui-accent-fg)] shadow-sm">
            <Sparkles className="h-6 w-6" />
          </div>
          <h1 className="text-2xl font-semibold text-[var(--phosphor-bright)]">Personal AI</h1>
          <p className="mt-2 text-sm leading-relaxed text-[var(--phosphor-dim)]">
            Sign in to access your conversations, documents, and smart chat history.
          </p>
        </div>

        {authConfig.google_auth_enabled ? (
          <div className="flex flex-col items-center gap-3">
            <div className={isSubmitting ? 'pointer-events-none opacity-60' : ''}>
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
                width="320"
              />
            </div>
            {isSubmitting && (
              <p className="text-xs text-[var(--phosphor-dim)]">Completing sign-in…</p>
            )}
          </div>
        ) : (
          <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
            Authentication is enabled but Google Sign-In is not configured. Set{' '}
            <code className="rounded bg-black/20 px-1 py-0.5 text-xs">GOOGLE_CLIENT_ID</code> on the server.
          </div>
        )}

        {error && (
          <div className="mt-4 rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-200">
            {error}
          </div>
        )}

        <p className="mt-6 text-center text-xs leading-relaxed text-[var(--phosphor-dim)]">
          Your conversations are private and tied to your account.
        </p>
      </div>
    </div>
  );
}
