import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  fetchAdminInvites,
  fetchAdminMe,
  fetchAdminProviders,
  fetchAdminRouting,
  fetchAdminSignupMode,
  fetchAdminUsageByUser,
  fetchAdminUsageSummary,
  fetchAdminUsers,
  createAdminInvite,
  createAdminProvider,
  updateAdminProvider,
  updateAdminRouting,
  updateAdminSignupMode,
  updateAdminUser,
  type AdminInvite,
  type AdminProvider,
  type AdminRouting,
  type AdminUsageByUser,
  type AdminUsageSummary,
  type AdminUserRow,
} from './adminApi';
import { clearAuthToken, getAuthToken } from './auth';
import { LoginPage } from './components/LoginPage';
import { CuraiLogo } from './components/CuraiLogo';
import { fetchAuthConfig, type AuthConfig } from './api';
import { GoogleOAuthProvider } from '@react-oauth/google';

type Tab = 'usage' | 'users' | 'invites' | 'providers' | 'routing' | 'access';

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

function humanizeError(raw: string): string {
  const trimmed = raw.trim();
  try {
    const parsed = JSON.parse(trimmed) as { detail?: string };
    if (parsed.detail) {
      return parsed.detail;
    }
  } catch {
    // keep text
  }
  return trimmed;
}

function AdminShell({ children }: { children: ReactNode }) {
  return (
    <div
      className="classic-font flex min-h-[100dvh] items-center justify-center bg-[var(--ui-bg)] px-4 py-10 text-[var(--phosphor)]"
      style={{
        paddingTop: 'max(2.5rem, var(--safe-area-top))',
        paddingBottom: 'max(2.5rem, var(--safe-area-bottom))',
      }}
    >
      {children}
    </div>
  );
}

export function AdminApp() {
  const [authConfig, setAuthConfig] = useState<AuthConfig | null>(null);
  const [tokenReady, setTokenReady] = useState(() => Boolean(getAuthToken()));
  const [me, setMe] = useState<{ role: string; email?: string | null; is_admin: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>('usage');

  useEffect(() => {
    void fetchAuthConfig()
      .then(setAuthConfig)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load auth config'));
  }, []);

  const refreshMe = useCallback(async () => {
    if (!getAuthToken()) {
      setMe(null);
      return;
    }
    const profile = await fetchAdminMe();
    setMe(profile);
  }, []);

  useEffect(() => {
    if (!tokenReady) return;
    void refreshMe().catch((err) => {
      setError(humanizeError(err instanceof Error ? err.message : 'Not authorized for admin'));
      setMe(null);
    });
  }, [tokenReady, refreshMe]);

  if (!authConfig) {
    return (
      <AdminShell>
        <div className="elevated-panel flex w-full max-w-md flex-col items-center rounded-2xl border border-[var(--ui-border)] p-8 text-center shadow-xl">
          <CuraiLogo state="thinking" size={48} className="mb-4" />
          <p className="text-sm text-[var(--phosphor-dim)]">Loading CurAI Admin…</p>
        </div>
      </AdminShell>
    );
  }

  if (!tokenReady || !getAuthToken()) {
    const login = (
      <LoginPage
        variant="admin"
        authConfig={authConfig}
        onAuthenticated={() => {
          setError(null);
          setTokenReady(true);
        }}
      />
    );
    if (authConfig.google_auth_enabled && authConfig.google_client_id) {
      return <GoogleOAuthProvider clientId={authConfig.google_client_id}>{login}</GoogleOAuthProvider>;
    }
    return login;
  }

  if (error && !me) {
    return (
      <AdminShell>
        <div className="elevated-panel w-full max-w-md rounded-2xl border border-[var(--ui-border)] p-6 shadow-xl sm:p-8">
          <div className="mb-6 flex flex-col items-center text-center">
            <CuraiLogo state="error" size={48} className="mb-4" />
            <h1 className="font-display text-2xl font-semibold tracking-tight text-[var(--phosphor-bright)]">
              CurAI Admin
            </h1>
            <p className="mt-2 text-sm font-medium text-[var(--phosphor-bright)]">Access denied</p>
            <p className="mt-2 text-sm leading-relaxed text-[var(--phosphor-dim)]">{error}</p>
          </div>
          <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-950 dark:text-amber-100">
            Your Google account signed in successfully, but it is not on the admin allowlist. Ask the owner to add your
            email to <code className="rounded bg-black/10 px-1 py-0.5 text-xs">ADMIN_EMAILS</code>, recreate the app,
            then try again.
          </div>
          <button
            type="button"
            className="touch-target mt-5 w-full rounded-full border border-[var(--ui-border-strong)] bg-[var(--ui-panel)] px-4 py-3 text-sm font-medium text-[var(--phosphor-bright)] transition hover:bg-[var(--ui-bg-elevated)]"
            onClick={() => {
              clearAuthToken();
              setTokenReady(false);
              setError(null);
            }}
          >
            Sign in with a different account
          </button>
        </div>
      </AdminShell>
    );
  }

  if (!me) {
    return (
      <AdminShell>
        <div className="elevated-panel flex w-full max-w-md flex-col items-center rounded-2xl border border-[var(--ui-border)] p-8 text-center shadow-xl">
          <CuraiLogo state="thinking" size={48} className="mb-4" />
          <p className="text-sm text-[var(--phosphor-dim)]">Checking admin access…</p>
        </div>
      </AdminShell>
    );
  }

  const tabs: Array<{ id: Tab; label: string; adminOnly?: boolean }> = [
    { id: 'usage', label: 'Usage' },
    { id: 'users', label: 'Users' },
    { id: 'invites', label: 'Invites' },
    { id: 'providers', label: 'Providers', adminOnly: true },
    { id: 'routing', label: 'Models', adminOnly: true },
    { id: 'access', label: 'Access', adminOnly: true },
  ];

  return (
    <div className="classic-font min-h-[100dvh] bg-[var(--ui-bg)] text-[var(--phosphor)]">
      <header className="flex items-center justify-between border-b border-[var(--ui-border)] bg-[var(--ui-panel)] px-4 py-3">
        <div className="flex items-center gap-3">
          <CuraiLogo state="idle" size={32} />
          <div>
            <p className="font-display text-sm font-semibold text-[var(--phosphor-bright)]">CurAI Admin</p>
            <p className="text-xs text-[var(--phosphor-dim)]">{me.email || me.role}</p>
          </div>
        </div>
        <button
          type="button"
          className="rounded-full border border-[var(--ui-border)] px-3 py-1.5 text-xs font-medium text-[var(--phosphor)] transition hover:bg-[var(--ui-bg-elevated)]"
          onClick={() => {
            clearAuthToken();
            setMe(null);
            setTokenReady(false);
            setError(null);
          }}
        >
          Sign out
        </button>
      </header>
      <nav className="flex flex-wrap gap-1 border-b border-[var(--ui-border)] px-3 py-2">
        {tabs
          .filter((item) => !item.adminOnly || me.is_admin)
          .map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setTab(item.id)}
              className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${
                tab === item.id
                  ? 'bg-[var(--ui-bg-elevated)] text-[var(--phosphor-bright)]'
                  : 'text-[var(--phosphor-dim)] hover:text-[var(--phosphor)]'
              }`}
            >
              {item.label}
            </button>
          ))}
      </nav>
      <main className="mx-auto max-w-5xl px-4 py-4">
        {tab === 'usage' && <UsagePanel />}
        {tab === 'users' && <UsersPanel isAdmin={me.is_admin} />}
        {tab === 'invites' && <InvitesPanel />}
        {tab === 'providers' && me.is_admin && <ProvidersPanel />}
        {tab === 'routing' && me.is_admin && <RoutingPanel />}
        {tab === 'access' && me.is_admin && <AccessPanel />}
      </main>
    </div>
  );
}

function UsagePanel() {
  const [summary, setSummary] = useState<AdminUsageSummary | null>(null);
  const [byUser, setByUser] = useState<AdminUsageByUser[]>([]);
  const [days, setDays] = useState(30);

  useEffect(() => {
    void Promise.all([fetchAdminUsageSummary(days), fetchAdminUsageByUser(days)]).then(([s, u]) => {
      setSummary(s);
      setByUser(u);
    });
  }, [days]);

  const max = useMemo(
    () => Math.max(1, ...(summary?.series.map((p) => p.total_tokens) || [1])),
    [summary],
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-semibold">Token usage</h2>
        <select
          className="rounded border border-[var(--ui-border)] bg-[var(--ui-panel)] px-2 py-1 text-xs"
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
        >
          <option value={7}>7 days</option>
          <option value={30}>30 days</option>
          <option value={90}>90 days</option>
        </select>
      </div>
      {summary && (
        <div className="grid gap-3 sm:grid-cols-3">
          <Stat label="Prompt" value={formatTokens(summary.prompt_tokens)} />
          <Stat label="Completion" value={formatTokens(summary.completion_tokens)} />
          <Stat label="Total" value={formatTokens(summary.total_tokens)} />
        </div>
      )}
      <div className="rounded-xl border border-[var(--ui-border)] bg-[var(--ui-panel)] p-3">
        <p className="mb-2 text-xs text-[var(--phosphor-dim)]">Daily totals</p>
        <div className="flex h-40 items-end gap-1">
          {(summary?.series || []).map((point) => (
            <div key={point.date} className="flex flex-1 flex-col items-center gap-1">
              <div
                className="w-full rounded-t bg-[var(--ui-focus)]/70"
                style={{ height: `${Math.max(4, (point.total_tokens / max) * 100)}%` }}
                title={`${point.date}: ${point.total_tokens}`}
              />
            </div>
          ))}
        </div>
      </div>
      <div className="overflow-x-auto rounded-xl border border-[var(--ui-border)]">
        <table className="w-full text-left text-xs">
          <thead className="bg-[var(--ui-panel)] text-[var(--phosphor-dim)]">
            <tr>
              <th className="px-3 py-2">User</th>
              <th className="px-3 py-2">Prompt</th>
              <th className="px-3 py-2">Completion</th>
              <th className="px-3 py-2">Total</th>
            </tr>
          </thead>
          <tbody>
            {byUser.map((row) => (
              <tr key={row.user_id || row.email || 'anon'} className="border-t border-[var(--ui-border)]">
                <td className="px-3 py-2">{row.email || row.display_name || row.user_id || 'anonymous'}</td>
                <td className="px-3 py-2 tabular-nums">{formatTokens(row.prompt_tokens)}</td>
                <td className="px-3 py-2 tabular-nums">{formatTokens(row.completion_tokens)}</td>
                <td className="px-3 py-2 tabular-nums">{formatTokens(row.total_tokens)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function UsersPanel({ isAdmin }: { isAdmin: boolean }) {
  const [users, setUsers] = useState<AdminUserRow[]>([]);
  const [q, setQ] = useState('');

  const load = useCallback(async () => {
    setUsers(await fetchAdminUsers(q || undefined));
  }, [q]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="space-y-3">
      <input
        className="w-full rounded-lg border border-[var(--ui-border)] bg-[var(--ui-panel)] px-3 py-2 text-sm"
        placeholder="Search email"
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      <div className="overflow-x-auto rounded-xl border border-[var(--ui-border)]">
        <table className="w-full text-left text-xs">
          <thead className="bg-[var(--ui-panel)] text-[var(--phosphor-dim)]">
            <tr>
              <th className="px-3 py-2">Email</th>
              <th className="px-3 py-2">Role</th>
              <th className="px-3 py-2">Active</th>
              <th className="px-3 py-2">Tokens</th>
              <th className="px-3 py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id} className="border-t border-[var(--ui-border)]">
                <td className="px-3 py-2">{user.email}</td>
                <td className="px-3 py-2">{user.role}</td>
                <td className="px-3 py-2">{user.is_active ? 'yes' : 'no'}</td>
                <td className="px-3 py-2 tabular-nums">{formatTokens(user.total_tokens)}</td>
                <td className="px-3 py-2">
                  <button
                    type="button"
                    className="mr-2 underline"
                    onClick={() => void updateAdminUser(user.id, { is_active: !user.is_active }).then(load)}
                  >
                    {user.is_active ? 'Disable' : 'Enable'}
                  </button>
                  {isAdmin && (
                    <select
                      className="rounded border border-[var(--ui-border)] bg-[var(--ui-panel)] px-1"
                      value={user.role}
                      onChange={(e) => void updateAdminUser(user.id, { role: e.target.value }).then(load)}
                    >
                      <option value="user">user</option>
                      <option value="support">support</option>
                      <option value="admin">admin</option>
                    </select>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function InvitesPanel() {
  const [invites, setInvites] = useState<AdminInvite[]>([]);
  const [email, setEmail] = useState('');

  const load = useCallback(async () => {
    setInvites(await fetchAdminInvites());
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="space-y-3">
      <form
        className="flex flex-wrap gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          void createAdminInvite({ email, role: 'user' }).then(() => {
            setEmail('');
            return load();
          });
        }}
      >
        <input
          required
          type="email"
          className="min-w-[220px] flex-1 rounded-lg border border-[var(--ui-border)] bg-[var(--ui-panel)] px-3 py-2 text-sm"
          placeholder="user@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <button type="submit" className="rounded-lg border border-[var(--ui-border)] px-3 py-2 text-sm">
          Create invite
        </button>
      </form>
      <ul className="space-y-2 text-xs">
        {invites.map((invite) => (
          <li key={invite.id} className="rounded-lg border border-[var(--ui-border)] bg-[var(--ui-panel)] px-3 py-2">
            <p className="font-medium">{invite.email}</p>
            <p className="text-[var(--phosphor-dim)]">
              {invite.role} · expires {new Date(invite.expires_at).toLocaleDateString()}
              {invite.accepted_at ? ' · accepted' : ''}
            </p>
            {invite.invite_url && (
              <p className="mt-1 break-all text-[var(--ui-focus)]">{invite.invite_url}</p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function ProvidersPanel() {
  const [providers, setProviders] = useState<AdminProvider[]>([]);
  const [form, setForm] = useState({ name: 'groq', display_name: 'Groq', base_url: 'https://api.groq.com/openai', api_key: '' });

  const load = useCallback(async () => {
    setProviders(await fetchAdminProviders());
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="space-y-4">
      <form
        className="grid gap-2 rounded-xl border border-[var(--ui-border)] bg-[var(--ui-panel)] p-3 sm:grid-cols-2"
        onSubmit={(e) => {
          e.preventDefault();
          void createAdminProvider({
            name: form.name,
            display_name: form.display_name,
            base_url: form.base_url,
            api_key: form.api_key || undefined,
            enabled: true,
          }).then(() => {
            setForm((current) => ({ ...current, api_key: '' }));
            return load();
          });
        }}
      >
        <input className="rounded border border-[var(--ui-border)] bg-[var(--ui-bg)] px-2 py-1.5 text-sm" placeholder="name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <input className="rounded border border-[var(--ui-border)] bg-[var(--ui-bg)] px-2 py-1.5 text-sm" placeholder="display name" value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} />
        <input className="rounded border border-[var(--ui-border)] bg-[var(--ui-bg)] px-2 py-1.5 text-sm sm:col-span-2" placeholder="base url" value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} />
        <input className="rounded border border-[var(--ui-border)] bg-[var(--ui-bg)] px-2 py-1.5 text-sm sm:col-span-2" placeholder="api key (write-only)" type="password" value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} />
        <button type="submit" className="rounded-lg border border-[var(--ui-border)] px-3 py-2 text-sm sm:col-span-2">
          Add provider
        </button>
      </form>
      <ul className="space-y-2 text-sm">
        {providers.map((provider) => (
          <li key={provider.id} className="rounded-xl border border-[var(--ui-border)] bg-[var(--ui-panel)] px-3 py-2">
            <div className="flex items-center justify-between gap-2">
              <div>
                <p className="font-medium">{provider.display_name}</p>
                <p className="text-xs text-[var(--phosphor-dim)]">
                  {provider.name} · {provider.base_url}
                  {provider.has_key ? ` · ****${provider.key_last4 || ''}` : ' · no key'}
                </p>
              </div>
              <button
                type="button"
                className="text-xs underline"
                onClick={() => void updateAdminProvider(provider.id, { enabled: !provider.enabled }).then(load)}
              >
                {provider.enabled ? 'Disable' : 'Enable'}
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function RoutingPanel() {
  const [routing, setRouting] = useState<AdminRouting | null>(null);

  useEffect(() => {
    void fetchAdminRouting().then(setRouting);
  }, []);

  if (!routing) return <p className="text-sm text-[var(--phosphor-dim)]">Loading…</p>;

  const fields: Array<keyof AdminRouting> = [
    'default_provider',
    'default_model',
    'planner_provider',
    'planner_model',
    'synthesizer_provider',
    'synthesizer_model',
    'reviewer_provider',
    'reviewer_model',
    'writer_provider',
    'writer_model',
  ];

  return (
    <form
      className="grid gap-2 sm:grid-cols-2"
      onSubmit={(e) => {
        e.preventDefault();
        void updateAdminRouting(routing).then(setRouting);
      }}
    >
      {fields.map((field) => (
        <label key={field} className="text-xs">
          <span className="mb-1 block text-[var(--phosphor-dim)]">{field}</span>
          <input
            className="w-full rounded border border-[var(--ui-border)] bg-[var(--ui-panel)] px-2 py-1.5 text-sm"
            value={routing[field]}
            onChange={(e) => setRouting({ ...routing, [field]: e.target.value })}
          />
        </label>
      ))}
      <button type="submit" className="rounded-lg border border-[var(--ui-border)] px-3 py-2 text-sm sm:col-span-2">
        Save routing
      </button>
    </form>
  );
}

function AccessPanel() {
  const [mode, setMode] = useState('invite');

  useEffect(() => {
    void fetchAdminSignupMode().then((res) => setMode(res.mode));
  }, []);

  return (
    <div className="space-y-3 rounded-xl border border-[var(--ui-border)] bg-[var(--ui-panel)] p-4">
      <p className="text-sm font-medium">Sign-up mode</p>
      <p className="text-xs text-[var(--phosphor-dim)]">
        Invite-only requires an admin invite (or ADMIN_EMAILS). Open allows any Google account after OAuth is published.
      </p>
      <select
        className="rounded border border-[var(--ui-border)] bg-[var(--ui-bg)] px-2 py-1.5 text-sm"
        value={mode}
        onChange={(e) => setMode(e.target.value)}
      >
        <option value="invite">invite</option>
        <option value="open">open</option>
      </select>
      <button
        type="button"
        className="block rounded-lg border border-[var(--ui-border)] px-3 py-2 text-sm"
        onClick={() => void updateAdminSignupMode(mode).then((res) => setMode(res.mode))}
      >
        Save
      </button>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-[var(--ui-border)] bg-[var(--ui-panel)] px-3 py-3">
      <p className="text-xs text-[var(--phosphor-dim)]">{label}</p>
      <p className="text-lg font-semibold tabular-nums text-[var(--phosphor-bright)]">{value}</p>
    </div>
  );
}