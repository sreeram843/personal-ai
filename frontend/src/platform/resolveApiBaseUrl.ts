export interface ResolveApiBaseUrlInput {
  configuredBaseUrl: string;
  hostname: string;
  isNativeShell: boolean;
}

/** Resolve the backend API origin for web and Capacitor shells. */
export function resolveApiBaseUrl({
  configuredBaseUrl,
  hostname,
  isNativeShell,
}: ResolveApiBaseUrlInput): string {
  const configured = configuredBaseUrl.trim();
  if (!configured) {
    return '';
  }

  if (isNativeShell) {
    return configured.replace(/\/$/, '');
  }

  const isLocalHost = hostname === 'localhost' || hostname === '127.0.0.1';
  const configuredIsLocal = configured.includes('localhost') || configured.includes('127.0.0.1');

  if (!isLocalHost && configuredIsLocal) {
    return '';
  }

  return configured.replace(/\/$/, '');
}
