import { describe, expect, it } from 'vitest';
import { prefersNativeGoogleSignIn } from './googleSignIn';

describe('prefersNativeGoogleSignIn', () => {
  it('returns false on web', () => {
    expect(prefersNativeGoogleSignIn(false, 'https:')).toBe(false);
  });

  it('returns false for cloud shell loading production over HTTPS', () => {
    expect(prefersNativeGoogleSignIn(true, 'https:')).toBe(false);
  });

  it('returns true for bundled capacitor:// shell', () => {
    expect(prefersNativeGoogleSignIn(true, 'capacitor:')).toBe(true);
  });
});
