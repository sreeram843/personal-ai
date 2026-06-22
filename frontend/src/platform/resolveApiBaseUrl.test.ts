import { describe, expect, it } from 'vitest';
import { resolveApiBaseUrl } from './resolveApiBaseUrl';

describe('resolveApiBaseUrl', () => {
  it('returns empty string when no API URL is configured', () => {
    expect(
      resolveApiBaseUrl({
        configuredBaseUrl: '',
        hostname: 'app.example.com',
        isNativeShell: false,
      }),
    ).toBe('');
  });

  it('uses same-origin fallback on web when configured URL is unset', () => {
    expect(
      resolveApiBaseUrl({
        configuredBaseUrl: 'http://localhost:8000',
        hostname: 'localhost',
        isNativeShell: false,
      }),
    ).toBe('http://localhost:8000');
  });

  it('ignores localhost API URL on remote web hosts', () => {
    expect(
      resolveApiBaseUrl({
        configuredBaseUrl: 'http://localhost:8000',
        hostname: 'app.example.com',
        isNativeShell: false,
      }),
    ).toBe('');
  });

  it('always uses configured API URL inside the Capacitor shell', () => {
    expect(
      resolveApiBaseUrl({
        configuredBaseUrl: 'http://localhost:8000',
        hostname: 'localhost',
        isNativeShell: true,
      }),
    ).toBe('http://localhost:8000');
  });

  it('strips trailing slashes from configured API URLs', () => {
    expect(
      resolveApiBaseUrl({
        configuredBaseUrl: 'https://api.example.com/',
        hostname: 'localhost',
        isNativeShell: true,
      }),
    ).toBe('https://api.example.com');
  });
});
