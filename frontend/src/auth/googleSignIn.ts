import { isCapacitorNative } from '../platform/capacitor';

export interface GoogleSignInResult {
  idToken: string;
}

let socialLoginInitialized = false;

async function initializeNativeGoogle(clientId: string): Promise<void> {
  if (socialLoginInitialized) {
    return;
  }

  const { SocialLogin } = await import('@capgo/capacitor-social-login');
  await SocialLogin.initialize({
    google: {
      webClientId: clientId,
    },
  });
  socialLoginInitialized = true;
}

export async function signInWithGoogle(clientId: string): Promise<GoogleSignInResult> {
  if (!isCapacitorNative()) {
    throw new Error('Native Google sign-in is only available in the Capacitor shell.');
  }

  await initializeNativeGoogle(clientId);
  const { SocialLogin } = await import('@capgo/capacitor-social-login');
  const response = await SocialLogin.login({
    provider: 'google',
    options: { scopes: ['email', 'profile'] },
  });

  if (response.result.responseType === 'offline') {
    throw new Error('Offline Google sign-in is not supported.');
  }

  const idToken = response.result.idToken?.trim();
  if (!idToken) {
    throw new Error('Google sign-in did not return an ID token.');
  }

  return { idToken };
}

export function shouldUseNativeGoogleSignIn(): boolean {
  return isCapacitorNative();
}
