import { GoogleOAuthProvider } from '@react-oauth/google';
import { useEffect, useState } from 'react';
import App from './App';
import { BootstrapScreen } from './components/BootstrapScreen';
import { LoginPage } from './components/LoginPage';
import { DemoApp } from './DemoApp';
import type { AuthConfig } from './api';
import { getAuthToken, AUTH_CHANGED_EVENT } from './auth';
import { useAuthBootstrap, useAuthConfig, useCurrentUser } from './query/hooks';

export function AppRoot({ demoMode = false }: { demoMode?: boolean }) {
  if (demoMode) {
    return <DemoApp />;
  }

  return <AuthenticatedAppRoot />;
}

function AuthenticatedAppRoot() {
  const configQuery = useAuthConfig();

  if (configQuery.isLoading) {
    return <BootstrapScreen />;
  }

  if (configQuery.isError || !configQuery.data) {
    return (
      <BootstrapScreen
        state="error"
        label={configQuery.error instanceof Error ? configQuery.error.message : 'Failed to load app configuration'}
      />
    );
  }

  const authConfig = configQuery.data;

  if (authConfig.google_auth_enabled && authConfig.google_client_id) {
    return (
      <GoogleOAuthProvider clientId={authConfig.google_client_id}>
        <AuthenticatedGate authConfig={authConfig} />
      </GoogleOAuthProvider>
    );
  }

  return <AuthenticatedGate authConfig={authConfig} />;
}

function AuthenticatedGate({ authConfig }: { authConfig: AuthConfig }) {
  const requiresLogin = !authConfig.auth_disabled;
  const [sessionReady, setSessionReady] = useState(() => Boolean(getAuthToken()));
  const hasToken = sessionReady || Boolean(getAuthToken());

  const devAuthQuery = useAuthBootstrap(authConfig.auth_disabled);
  const devReady = !authConfig.auth_disabled || devAuthQuery.isSuccess;
  const sessionActive = devReady && hasToken;
  const currentUserQuery = useCurrentUser(sessionActive);

  useEffect(() => {
    if (authConfig.auth_disabled && devAuthQuery.isSuccess) {
      setSessionReady(true);
    }
  }, [authConfig.auth_disabled, devAuthQuery.isSuccess]);

  useEffect(() => {
    const syncSession = () => setSessionReady(Boolean(getAuthToken()));
    window.addEventListener(AUTH_CHANGED_EVENT, syncSession);
    return () => window.removeEventListener(AUTH_CHANGED_EVENT, syncSession);
  }, []);

  if (authConfig.auth_disabled && devAuthQuery.isLoading) {
    return <BootstrapScreen />;
  }

  if (authConfig.auth_disabled && devAuthQuery.isError) {
    return (
      <BootstrapScreen
        state="error"
        label={devAuthQuery.error instanceof Error ? devAuthQuery.error.message : 'Failed to start dev session'}
      />
    );
  }

  if (requiresLogin && !hasToken) {
    return (
      <LoginPage
        authConfig={authConfig}
        onAuthenticated={() => setSessionReady(true)}
      />
    );
  }

  if (sessionActive && currentUserQuery.isLoading) {
    return <BootstrapScreen />;
  }

  if (requiresLogin && sessionActive && (currentUserQuery.isError || !currentUserQuery.data)) {
    return (
      <LoginPage
        authConfig={authConfig}
        onAuthenticated={() => setSessionReady(true)}
      />
    );
  }

  if (!currentUserQuery.data) {
    return <BootstrapScreen />;
  }

  return <App authConfig={authConfig} user={currentUserQuery.data} />;
}
