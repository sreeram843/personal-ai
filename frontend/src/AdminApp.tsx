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
import { fetchAuthConfig, ensureAuthToken, type AuthConfig, type CurrentUser } from './api';
import { GoogleOAuthProvider } from '@react-oauth/google';
import { useTheme } from './hooks/useTheme';
import { userInitials, userLabel } from './utils/userDisplay';

type Tab = 'users' | 'invites' | 'providers' | 'routing' | 'usage' | 'access';

const TAB_TITLES: Record<Tab, string> = {
  users: 'Users',
  invites: 'Invites',
  providers: 'Providers',
  routing: 'Model routing',
  usage: 'Usage',
  access: 'Access',
};

const NAV_LABELS: Record<Tab, string> = {
  users: 'Users',
  invites: 'Invites',
  providers: 'Providers',
  routing: 'Routing',
  usage: 'Usage',
  access: 'Access',
};

function formatTokens(n: number): string {
  if (n >= 1_000_000) {
    const value = n / 1_000_000;
    return `${Number.isInteger(value) ? value.toFixed(0) : value.toFixed(1)}M`;
  }
  if (n >= 1_000) {
    const value = n / 1_000;
    return `${Number.isInteger(value) ? value.toFixed(0) : value.toFixed(1)}k`;
  }
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
      className="flex min-h-[100dvh] items-center justify-center bg-[var(--ui-bg)] px-4 py-10 text-[var(--phosphor)]"
      style={{
        paddingTop: 'max(2.5rem, var(--safe-area-top))',
        paddingBottom: 'max(2.5rem, var(--safe-area-bottom))',
      }}
    >
      {children}
    </div>
  );
}

function NavItem({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button type="button" className="admin-nav-item" data-active={active} onClick={onClick}>
      {label}
    </button>
  );
}

export function AdminApp() {
  const [theme, , toggleTheme] = useTheme();
  const [authConfig, setAuthConfig] = useState<AuthConfig | null>(null);
  const [tokenReady, setTokenReady] = useState(() => Boolean(getAuthToken()));
  const [me, setMe] = useState<{
    id?: string;
    role: string;
    email?: string | null;
    display_name?: string | null;
    is_admin: boolean;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>('users');

  useEffect(() => {
    void fetchAuthConfig()
      .then(setAuthConfig)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load auth config'));
  }, []);

  useEffect(() => {
    if (!authConfig?.auth_disabled || tokenReady) return;
    void ensureAuthToken()
      .then(() => {
        setError(null);
        setTokenReady(true);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to start local admin session');
      });
  }, [authConfig, tokenReady]);

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
        <div className="admin-panel flex w-full max-w-md flex-col items-center p-8 text-center">
          <CuraiLogo state="thinking" size={48} className="mb-4" />
          <p className="text-sm text-[var(--phosphor-dim)]">Loading CurAI Admin…</p>
        </div>
      </AdminShell>
    );
  }

  if (authConfig.auth_disabled && !tokenReady) {
    return (
      <AdminShell>
        <div className="admin-panel flex w-full max-w-md flex-col items-center p-8 text-center">
          <CuraiLogo state="thinking" size={48} className="mb-4" />
          <p className="text-sm text-[var(--phosphor-dim)]">Starting local admin session…</p>
          {error && <p className="mt-3 text-sm text-red-400">{error}</p>}
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
        <div className="admin-panel w-full max-w-md p-6 sm:p-8">
          <div className="mb-6 flex flex-col items-center text-center">
            <CuraiLogo state="error" size={48} className="mb-4" />
            <h1 className="text-2xl font-semibold tracking-tight text-[var(--phosphor-bright)]">CurAI Admin</h1>
            <p className="mt-2 text-sm font-medium text-[var(--phosphor-bright)]">Access denied</p>
            <p className="mt-2 text-sm leading-relaxed text-[var(--phosphor-dim)]">{error}</p>
          </div>
          <div className="rounded-[10px] border border-[rgba(224,164,70,0.35)] bg-[rgba(224,164,70,0.1)] px-4 py-3 text-sm text-[var(--text-primary)]">
            Your Google account signed in successfully, but it is not on the admin allowlist. Ask the owner to add your
            email to <code className="rounded bg-black/10 px-1 py-0.5 text-xs dark:bg-white/10">ADMIN_EMAILS</code>,
            recreate the app, then try again.
          </div>
          <button
            type="button"
            className="admin-btn-ghost mt-5 w-full py-3 text-sm font-medium"
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
        <div className="admin-panel flex w-full max-w-md flex-col items-center p-8 text-center">
          <CuraiLogo state="thinking" size={48} className="mb-4" />
          <p className="text-sm text-[var(--phosphor-dim)]">Checking admin access…</p>
        </div>
      </AdminShell>
    );
  }

  const profileUser: CurrentUser = {
    id: me.id || 'admin',
    email: me.email,
    display_name: me.display_name,
  };

  const platformTabs: Tab[] = ['users', 'invites'];
  const routingTabs: Tab[] = me.is_admin ? ['providers', 'routing'] : [];
  const insightTabs: Tab[] = me.is_admin ? ['usage', 'access'] : ['usage'];

  return (
    <div className="admin-app">
      <aside className="admin-sidebar">
        <div className="mb-[22px] flex items-center gap-[9px] px-1.5">
          <CuraiLogo state="idle" size={26} />
          <span className="text-[15px] font-bold text-[var(--text-primary)]">CurAI</span>
          <span className="ml-auto rounded-md bg-[rgba(224,164,70,0.14)] px-[7px] py-0.5 text-[10px] font-bold tracking-[0.06em] text-[var(--ui-accent)]">
            ADMIN
          </span>
        </div>

        <div className="admin-nav-eyebrow">Platform</div>
        {platformTabs.map((id) => (
          <NavItem key={id} label={NAV_LABELS[id]} active={tab === id} onClick={() => setTab(id)} />
        ))}

        {routingTabs.length > 0 && (
          <>
            <div className="admin-nav-eyebrow !pt-3.5">Model routing</div>
            {routingTabs.map((id) => (
              <NavItem key={id} label={NAV_LABELS[id]} active={tab === id} onClick={() => setTab(id)} />
            ))}
          </>
        )}

        <div className="admin-nav-eyebrow !pt-3.5">Insights</div>
        {insightTabs.map((id) => (
          <NavItem key={id} label={NAV_LABELS[id]} active={tab === id} onClick={() => setTab(id)} />
        ))}

        <div className="flex-1" />

        <div className="mt-2 flex items-center gap-2.5 border-t border-[var(--ui-border)] px-2 pb-1 pt-4">
          <div className="grid h-7 w-7 shrink-0 place-content-center rounded-full bg-[var(--ui-accent)] text-[11px] font-bold text-[var(--ui-accent-fg)]">
            {userInitials(profileUser)}
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-[12.5px] font-semibold text-[var(--text-primary)]">{userLabel(profileUser)}</div>
            <div className="truncate text-[10.5px] text-[var(--phosphor-dim)]">{me.role}</div>
          </div>
          <button
            type="button"
            className="admin-btn-ghost shrink-0 px-2 py-1 text-[11px]"
            onClick={() => {
              clearAuthToken();
              setMe(null);
              setTokenReady(false);
              setError(null);
            }}
          >
            Sign out
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-[var(--ui-border)] px-8 py-[18px]">
          <h1 className="text-[19px] font-bold text-[var(--text-primary)]">{TAB_TITLES[tab]}</h1>
          <button type="button" className="admin-btn-ghost" onClick={toggleTheme}>
            {theme === 'dark' ? 'Light mode' : 'Dark mode'}
          </button>
        </header>

        <main className="flex-1 overflow-y-auto px-8 py-6">
          {tab === 'users' && <UsersPanel isAdmin={me.is_admin} />}
          {tab === 'invites' && <InvitesPanel />}
          {tab === 'providers' && me.is_admin && <ProvidersPanel />}
          {tab === 'routing' && me.is_admin && <RoutingPanel />}
          {tab === 'usage' && <UsagePanel />}
          {tab === 'access' && me.is_admin && <AccessPanel />}
        </main>
      </div>
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

  const max = useMemo(() => Math.max(1, ...(summary?.series.map((p) => p.total_tokens) || [1])), [summary]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-end">
        <select className="admin-input py-1.5 text-xs" value={days} onChange={(e) => setDays(Number(e.target.value))}>
          <option value={7}>7 days</option>
          <option value={30}>30 days</option>
          <option value={90}>90 days</option>
        </select>
      </div>

      {summary && (
        <div className="flex flex-col gap-3.5 sm:flex-row">
          <div className="admin-panel flex-1">
            <div className="text-[11px] font-semibold uppercase tracking-[0.05em] text-[var(--phosphor-dim)]">
              Prompt tokens
            </div>
            <div className="mt-1.5 text-[26px] font-bold tabular-nums text-[var(--text-primary)]">
              {formatTokens(summary.prompt_tokens)}
            </div>
          </div>
          <div className="admin-panel flex-1">
            <div className="text-[11px] font-semibold uppercase tracking-[0.05em] text-[var(--phosphor-dim)]">
              Completion tokens
            </div>
            <div className="mt-1.5 text-[26px] font-bold tabular-nums text-[var(--text-primary)]">
              {formatTokens(summary.completion_tokens)}
            </div>
          </div>
          <div className="admin-panel flex-1">
            <div className="text-[11px] font-semibold uppercase tracking-[0.05em] text-[var(--phosphor-dim)]">
              Total tokens
            </div>
            <div className="mt-1.5 text-[26px] font-bold tabular-nums text-[var(--ui-accent)]">
              {formatTokens(summary.total_tokens)}
            </div>
          </div>
        </div>
      )}

      <div className="admin-panel">
        <div className="mb-3.5 text-[12.5px] font-semibold text-[var(--text-primary)]">
          Daily usage — last {days} days
        </div>
        <div className="flex h-[120px] items-end gap-1.5">
          {(summary?.series || []).map((point) => (
            <div
              key={point.date}
              className="flex-1 rounded-t bg-[var(--ui-accent)]"
              style={{ height: `${Math.max(8, (point.total_tokens / max) * 100)}%` }}
              title={`${point.date}: ${point.total_tokens}`}
            />
          ))}
        </div>
      </div>

      <div className="admin-panel overflow-hidden p-0">
        <div className="admin-table-head grid-cols-[1.6fr_0.7fr_0.7fr_0.7fr]">
          <div>User</div>
          <div>Prompt</div>
          <div>Completion</div>
          <div>Total</div>
        </div>
        {byUser.map((row) => (
          <div
            key={row.user_id || row.email || 'anon'}
            className="admin-table-row grid-cols-[1.6fr_0.7fr_0.7fr_0.7fr]"
          >
            <div className="truncate">{row.email || row.display_name || row.user_id || 'anonymous'}</div>
            <div className="tabular-nums">{formatTokens(row.prompt_tokens)}</div>
            <div className="tabular-nums">{formatTokens(row.completion_tokens)}</div>
            <div className="tabular-nums">{formatTokens(row.total_tokens)}</div>
          </div>
        ))}
        {byUser.length === 0 && (
          <div className="px-[18px] py-6 text-[13px] text-[var(--phosphor-dim)]">No usage in this window.</div>
        )}
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
    <div className="space-y-4">
      <input
        className="admin-input w-full max-w-md"
        placeholder="Search email"
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      <div className="admin-panel overflow-hidden p-0">
        <div className="admin-table-head grid-cols-[1.6fr_0.7fr_0.6fr_0.8fr_0.9fr]">
          <div>User</div>
          <div>Role</div>
          <div>Active</div>
          <div>Conversations</div>
          <div>Tokens</div>
        </div>
        {users.map((user) => (
          <div key={user.id} className="admin-table-row grid-cols-[1.6fr_0.7fr_0.6fr_0.8fr_0.9fr]">
            <div className="min-w-0">
              <div className="truncate text-[13.5px] font-semibold text-[var(--text-primary)]">
                {user.display_name || user.email || 'User'}
              </div>
              <div className="truncate text-[11.5px] text-[var(--phosphor-dim)]">{user.email}</div>
            </div>
            <div>
              {isAdmin ? (
                <select
                  className="admin-input py-1 text-[12.5px]"
                  value={user.role}
                  onChange={(e) => void updateAdminUser(user.id, { role: e.target.value }).then(load)}
                >
                  <option value="user">user</option>
                  <option value="support">support</option>
                  <option value="admin">admin</option>
                </select>
              ) : (
                user.role
              )}
            </div>
            <div>
              <button
                type="button"
                onClick={() => void updateAdminUser(user.id, { is_active: !user.is_active }).then(load)}
                className={user.is_active ? 'admin-badge-active' : 'admin-badge-disabled'}
                title={user.is_active ? 'Click to disable' : 'Click to enable'}
              >
                {user.is_active ? 'Active' : 'Disabled'}
              </button>
            </div>
            <div className="tabular-nums">{user.conversation_count}</div>
            <div className="tabular-nums">{formatTokens(user.total_tokens)}</div>
          </div>
        ))}
        {users.length === 0 && (
          <div className="px-[18px] py-6 text-[13px] text-[var(--phosphor-dim)]">No users found.</div>
        )}
      </div>
    </div>
  );
}

function InvitesPanel() {
  const [invites, setInvites] = useState<AdminInvite[]>([]);
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('user');

  const load = useCallback(async () => {
    setInvites(await fetchAdminInvites());
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="space-y-4">
      <form
        className="admin-panel flex flex-col gap-2.5 sm:flex-row sm:items-center"
        onSubmit={(e) => {
          e.preventDefault();
          void createAdminInvite({ email, role }).then(() => {
            setEmail('');
            return load();
          });
        }}
      >
        <input
          required
          type="email"
          className="admin-input min-w-0 flex-1"
          placeholder="teammate@company.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <select className="admin-input py-2 text-[13px]" value={role} onChange={(e) => setRole(e.target.value)}>
          <option value="user">user</option>
          <option value="support">support</option>
          <option value="admin">admin</option>
        </select>
        <button type="submit" className="admin-btn-primary shrink-0">
          + Send invite
        </button>
      </form>

      <div className="admin-panel overflow-hidden p-0">
        <div className="admin-table-head grid-cols-[1.4fr_0.7fr_0.8fr_0.8fr]">
          <div>Email</div>
          <div>Role</div>
          <div>Expires</div>
          <div>Status</div>
        </div>
        {invites.map((invite) => (
          <div key={invite.id} className="admin-table-row grid-cols-[1.4fr_0.7fr_0.8fr_0.8fr]">
            <div className="min-w-0">
              <div className="truncate">{invite.email}</div>
              {invite.invite_url && (
                <div className="mt-0.5 truncate text-[11px] text-[var(--ui-accent)]">{invite.invite_url}</div>
              )}
            </div>
            <div>{invite.role}</div>
            <div>{new Date(invite.expires_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</div>
            <div className={invite.accepted_at ? 'text-[#6fcf97]' : 'text-[var(--phosphor-dim)]'}>
              {invite.accepted_at ? 'Accepted' : 'Pending'}
            </div>
          </div>
        ))}
        {invites.length === 0 && (
          <div className="px-[18px] py-6 text-[13px] text-[var(--phosphor-dim)]">No invites yet.</div>
        )}
      </div>
    </div>
  );
}

const PROVIDER_PRESETS = [
  {
    name: 'groq',
    display_name: 'Groq',
    base_url: 'https://api.groq.com/openai',
    modelHint: 'llama-3.1-8b-instant',
  },
  {
    name: 'perplexity',
    display_name: 'Perplexity',
    base_url: 'https://api.perplexity.ai',
    modelHint: 'sonar-pro',
  },
  {
    name: 'gemini',
    display_name: 'Google Gemini',
    base_url: 'https://generativelanguage.googleapis.com/v1beta/openai',
    modelHint: 'gemini-flash-latest',
  },
  {
    name: 'openai',
    display_name: 'OpenAI',
    base_url: 'https://api.openai.com',
    modelHint: 'gpt-4o-mini',
  },
  {
    name: 'deepseek',
    display_name: 'DeepSeek',
    base_url: 'https://api.deepseek.com',
    modelHint: 'deepseek-chat',
  },
] as const;

function ProvidersPanel() {
  const [providers, setProviders] = useState<AdminProvider[]>([]);
  const [form, setForm] = useState({
    name: 'groq',
    display_name: 'Groq',
    base_url: 'https://api.groq.com/openai',
    api_key: '',
  });
  const [modelHint, setModelHint] = useState('llama-3.1-8b-instant');
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setProviders(await fetchAdminProviders());
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const applyPreset = (preset: (typeof PROVIDER_PRESETS)[number]) => {
    setForm({
      name: preset.name,
      display_name: preset.display_name,
      base_url: preset.base_url,
      api_key: form.api_key,
    });
    setModelHint(preset.modelHint);
    setError(null);
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-2">
        {PROVIDER_PRESETS.map((preset) => (
          <button
            key={preset.name}
            type="button"
            className="admin-btn-ghost rounded-full px-3 py-1 text-[12px]"
            onClick={() => applyPreset(preset)}
          >
            {preset.display_name}
          </button>
        ))}
      </div>
      <form
        className="admin-panel grid gap-2 sm:grid-cols-2"
        onSubmit={(e) => {
          e.preventDefault();
          setError(null);
          void createAdminProvider({
            name: form.name,
            display_name: form.display_name,
            base_url: form.base_url,
            api_key: form.api_key || undefined,
            enabled: true,
          })
            .then(() => {
              setForm((current) => ({ ...current, api_key: '' }));
              return load();
            })
            .catch((err: unknown) => {
              setError(err instanceof Error ? err.message : 'Failed to add provider');
            });
        }}
      >
        <input
          className="admin-input"
          placeholder="name"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
        />
        <input
          className="admin-input"
          placeholder="display name"
          value={form.display_name}
          onChange={(e) => setForm({ ...form, display_name: e.target.value })}
        />
        <input
          className="admin-input sm:col-span-2"
          placeholder="base url"
          value={form.base_url}
          onChange={(e) => setForm({ ...form, base_url: e.target.value })}
        />
        <input
          className="admin-input sm:col-span-2"
          placeholder="api key (write-only)"
          type="password"
          value={form.api_key}
          onChange={(e) => setForm({ ...form, api_key: e.target.value })}
        />
        <p className="sm:col-span-2 text-[12px] text-[var(--phosphor-dim)]">
          Suggested routing model id: <span className="font-mono text-[var(--ui-accent)]">{modelHint}</span>
          {form.name === 'perplexity' && (
            <> · Note: <span className="font-mono">PERPLEXITY_API_KEY</span> in env is still used for web search; this provider is for Sonar chat.</>
          )}
        </p>
        {error && <p className="sm:col-span-2 text-[12.5px] text-red-400">{error}</p>}
        <button type="submit" className="admin-btn-primary sm:col-span-2">
          + Add provider
        </button>
      </form>

      {providers.map((provider) => (
        <div key={provider.id} className="admin-panel flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="text-[14px] font-semibold text-[var(--text-primary)]">{provider.display_name}</div>
            <div className="truncate font-mono text-[12px] text-[var(--phosphor-dim)]">
              {provider.base_url}
              {provider.has_key ? ` · key ····${provider.key_last4 || ''}` : ' · no key'}
            </div>
          </div>
          <button
            type="button"
            className="admin-toggle shrink-0"
            data-on={provider.enabled}
            aria-pressed={provider.enabled}
            aria-label={`${provider.enabled ? 'Disable' : 'Enable'} ${provider.display_name}`}
            onClick={() => void updateAdminProvider(provider.id, { enabled: !provider.enabled }).then(load)}
          >
            <div className="admin-toggle-knob" />
          </button>
        </div>
      ))}
    </div>
  );
}

function RoutingPanel() {
  const [routing, setRouting] = useState<AdminRouting | null>(null);
  const [providers, setProviders] = useState<AdminProvider[]>([]);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void Promise.all([fetchAdminRouting(), fetchAdminProviders()]).then(([nextRouting, nextProviders]) => {
      setRouting(nextRouting);
      setProviders(nextProviders.filter((p) => p.enabled));
    });
  }, []);

  if (!routing) {
    return <p className="text-sm text-[var(--phosphor-dim)]">Loading…</p>;
  }

  const providerOptions = Array.from(
    new Set([
      'ollama',
      'openai',
      ...providers.map((p) => p.name),
      routing.default_provider,
      routing.planner_provider,
      routing.synthesizer_provider,
      routing.reviewer_provider,
      routing.writer_provider,
    ]),
  );

  const rows: Array<{ label: string; providerKey: keyof AdminRouting; modelKey: keyof AdminRouting }> = [
    { label: 'Default', providerKey: 'default_provider', modelKey: 'default_model' },
    { label: 'Planner', providerKey: 'planner_provider', modelKey: 'planner_model' },
    { label: 'Synthesizer', providerKey: 'synthesizer_provider', modelKey: 'synthesizer_model' },
    { label: 'Reviewer', providerKey: 'reviewer_provider', modelKey: 'reviewer_model' },
    { label: 'Writer', providerKey: 'writer_provider', modelKey: 'writer_model' },
  ];

  return (
    <form
      className="flex flex-col gap-2.5"
      onSubmit={(e) => {
        e.preventDefault();
        setError(null);
        void updateAdminRouting(routing)
          .then((next) => {
            setRouting(next);
            setSaved(true);
            window.setTimeout(() => setSaved(false), 1600);
          })
          .catch((err: unknown) => {
            setError(err instanceof Error ? err.message : 'Failed to save routing');
          });
      }}
    >
      <p className="text-[12.5px] text-[var(--phosphor-dim)]">
        Each stage can use a different enabled provider. Model ids must match that vendor (e.g. Groq{' '}
        <span className="font-mono">llama-3.1-8b-instant</span>).
      </p>
      {rows.map((row) => (
        <div key={row.label} className="admin-panel flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="text-[13.5px] font-semibold text-[var(--text-primary)]">{row.label}</div>
          <div className="flex flex-wrap items-center gap-2 font-mono text-[12.5px] text-[var(--phosphor-dim)]">
            <select
              className="admin-input min-w-[140px] py-1.5"
              value={routing[row.providerKey]}
              onChange={(e) => setRouting({ ...routing, [row.providerKey]: e.target.value })}
            >
              {providerOptions.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
            <span>/</span>
            <input
              className="admin-input min-w-[180px] py-1.5"
              value={routing[row.modelKey]}
              onChange={(e) => setRouting({ ...routing, [row.modelKey]: e.target.value })}
              placeholder="model id"
            />
          </div>
        </div>
      ))}
      {error && <p className="text-[12.5px] text-red-400">{error}</p>}
      <button type="submit" className="admin-btn-primary self-start">
        {saved ? 'Saved' : 'Save routing'}
      </button>
    </form>
  );
}

function AccessPanel() {
  const [mode, setMode] = useState('invite');
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    void fetchAdminSignupMode().then((res) => setMode(res.mode));
  }, []);

  const save = (next: string) => {
    setMode(next);
    void updateAdminSignupMode(next).then((res) => {
      setMode(res.mode);
      setSaved(true);
      window.setTimeout(() => setSaved(false), 1600);
    });
  };

  return (
    <div className="admin-panel max-w-xl">
      <div className="mb-1 text-[14px] font-semibold text-[var(--text-primary)]">Sign-up mode</div>
      <div className="mb-4 text-[13px] text-[var(--ui-text-secondary)]">Choose who can create a new account.</div>
      <button type="button" className="admin-pick-card" data-active={mode === 'open'} onClick={() => save('open')}>
        <div className="text-[13.5px] font-semibold text-[var(--text-primary)]">Open</div>
        <div className="mt-0.5 text-[12px] text-[var(--ui-text-secondary)]">Anyone can sign up with Google.</div>
      </button>
      <button
        type="button"
        className="admin-pick-card"
        data-active={mode === 'invite'}
        onClick={() => save('invite')}
      >
        <div className="text-[13.5px] font-semibold text-[var(--text-primary)]">Invite-only</div>
        <div className="mt-0.5 text-[12px] text-[var(--ui-text-secondary)]">Sign-up requires a pending invite.</div>
      </button>
      {saved && <p className="mt-1 text-[12px] text-[#6fcf97]">Saved</p>}
    </div>
  );
}
