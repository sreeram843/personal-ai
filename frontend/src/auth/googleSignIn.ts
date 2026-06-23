import { isCapacitorNative } from '../platform/capacitor';

export interface GoogleSignInResult {
  idToken: string;
}

let socialLoginInitialized = false;

/** Testable: native SDK only for bundled capacitor:// shell, not remote HTTPS WebView. */
export function prefersNativeGoogleSignIn(
  isNative: boolean,
  pageProtocol: string,
): boolean {
  if (!isNative) {
    return false;
  }
  return pageProtocol !== 'https:';
}

/**
 * Native Google SDK is only for bundled capacitor:// shells.
 * Cloud shell mode loads https://app.cura-i.com — use web OAuth (@react-oauth/google) instead.
 */
export function shouldUseNativeGoogleSignIn(): boolean {
  if (typeof window === 'undefined') {
    return false;
  }
  return prefersNativeGoogleSignIn(isCapacitorNative(), window.location.protocol);
}

async function initializeNativeGoogle(clientId: string): Promise<void> {
  if (socialLoginInitialized) {
    return;
  }

  const iosClientId = ((import.meta.env.VITE_GOOGLE_IOS_CLIENT_ID as string) || '').trim() || clientId;

  const { SocialLogin } = await import('@capgo/capacitor-social-login');
  await SocialLogin.initialize({
    google: {
      webClientId: clientId,
      iOSClientId: iosClientId,
      mode: 'online',
    },
  });
  socialLoginInitialized = true;
}

export async function signInWithGoogle(clientId: string): Promise<GoogleSignInResult> {
  if (!shouldUseNativeGoogleSignIn()) {
    throw new Error('Native Google sign-in is only available in the bundled Capacitor shell.');
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
