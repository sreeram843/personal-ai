import { clsx } from 'clsx';
import {
  Activity,
  Bot,
  CheckCircle2,
  Circle,
  ListTodo,
  Palette,
  Plug,
  Shield,
  Sparkles,
  Trash2,
  User,
  X,
  Zap,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import type { AuthConfig, CurrentUser } from '../api';
import {
  createMcpServer,
  deleteAgentTask,
  deleteMcpServer,
  fetchAgentTasks,
  fetchDoctorReport,
  fetchMcpServers,
  fetchSkills,
  testMcpServer,
  updateAgentTaskStatus,
  updateSkill,
} from '../api';
import type {
  AgentTaskSummary,
  DoctorReport,
  McpServerSummary,
  SkillSummary,
  ToolPermissionMode,
} from '../types';
import { AppearancePanel } from './AppearancePanel';
import { AssistantsPanel } from './AssistantsPanel';
import { ProfilePanel } from './ProfilePanel';

const PERMISSION_OPTIONS: Array<{ value: ToolPermissionMode; label: string; hint: string }> = [
  { value: 'auto', label: 'Auto', hint: 'Run read tools automatically; audit write/MCP tools.' },
  { value: 'ask', label: 'Ask', hint: 'Pause on external/write tools until you approve.' },
  { value: 'plan', label: 'Plan', hint: 'Describe tool calls without executing them.' },
];

type TabId =
  | 'profile'
  | 'appearance'
  | 'permissions'
  | 'mcp'
  | 'skills'
  | 'assistants'
  | 'tasks'
  | 'diagnostics';

const TAB_META: Record<TabId, { label: string; description: string; icon: typeof Shield }> = {
  profile: {
    label: 'Profile',
    description: 'Your account details and sign-in identity.',
    icon: User,
  },
  appearance: {
    label: 'Appearance',
    description: 'Choose light or dark mode for the interface.',
    icon: Palette,
  },
  permissions: {
    label: 'Permissions',
    description: 'Choose when tools run automatically, pause for approval, or stay in plan-only mode.',
    icon: Shield,
  },
  mcp: {
    label: 'MCP',
    description: 'Connect Model Context Protocol servers to extend available tools.',
    icon: Plug,
  },
  skills: {
    label: 'Skills',
    description: 'Toggle bundled skills and review trigger phrases.',
    icon: Sparkles,
  },
  assistants: {
    label: 'Assistants',
    description: 'Create pick-only assistants with custom instructions and tool limits.',
    icon: Bot,
  },
  tasks: {
    label: 'Tasks',
    description: 'Review planned tools and pending items from agent runs.',
    icon: ListTodo,
  },
  diagnostics: {
    label: 'Doctor',
    description: 'Run health checks on runtime components and connectors.',
    icon: Activity,
  },
};

const NAV_GROUPS: Array<{ label: string; tabs: TabId[] }> = [
  { label: 'Account', tabs: ['profile', 'appearance'] },
  { label: 'Agent', tabs: ['permissions', 'mcp', 'skills', 'assistants', 'tasks'] },
  { label: 'Health', tabs: ['diagnostics'] },
];

const FETCH_TABS = new Set<TabId>(['mcp', 'skills', 'tasks', 'diagnostics']);

interface Props {
  open: boolean;
  onClose: () => void;
  user: CurrentUser;
  authConfig: AuthConfig;
  theme: 'light' | 'dark';
  onSetTheme: (theme: 'light' | 'dark') => void;
  toolPermissionMode: ToolPermissionMode;
  onToolPermissionModeChange: (mode: ToolPermissionMode) => void;
  onAccountDeleted?: () => void;
}

export function SettingsPanel({
  open,
  onClose,
  user,
  authConfig,
  theme,
  onSetTheme,
  toolPermissionMode,
  onToolPermissionModeChange,
  onAccountDeleted,
}: Props) {
  const [tab, setTab] = useState<TabId>('profile');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [servers, setServers] = useState<McpServerSummary[]>([]);
  const [name, setName] = useState('GitHub');
  const [url, setUrl] = useState('https://api.githubcopilot.com/mcp/readonly');
  const [authHeader, setAuthHeader] = useState('');
  const [testingId, setTestingId] = useState<string | null>(null);

  const [skills, setSkills] = useState<SkillSummary[]>([]);
  const [tasks, setTasks] = useState<AgentTaskSummary[]>([]);
  const [doctor, setDoctor] = useState<DoctorReport | null>(null);

  const activeMeta = TAB_META[tab];

  const refreshTab = async (target: TabId) => {
    setLoading(true);
    setError(null);
    try {
      if (target === 'mcp') {
        setServers(await fetchMcpServers());
      } else if (target === 'skills') {
        setSkills(await fetchSkills());
      } else if (target === 'tasks') {
        setTasks(await fetchAgentTasks());
      } else if (target === 'diagnostics') {
        setDoctor(await fetchDoctorReport());
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open && FETCH_TABS.has(tab)) {
      void refreshTab(tab);
    }
  }, [open, tab]);

  if (!open) {
    return null;
  }

  const handleAddMcp = async () => {
    setError(null);
    try {
      const headers: Record<string, string> = {};
      if (authHeader.trim()) {
        headers.Authorization = authHeader.trim().startsWith('Bearer ')
          ? authHeader.trim()
          : `Bearer ${authHeader.trim()}`;
      }
      await createMcpServer({ name: name.trim(), url: url.trim(), enabled: true, headers });
      setAuthHeader('');
      await refreshTab('mcp');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add MCP server');
    }
  };

  return (
    <div className="settings-backdrop fixed inset-0 z-50 flex items-end justify-center p-3 sm:items-center sm:p-6">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
        className="settings-dialog flex max-h-[min(600px,92vh)] w-full max-w-[920px] flex-col overflow-hidden"
      >
        <button
          type="button"
          onClick={onClose}
          className="settings-dialog-close touch-target grid h-9 w-9 place-content-center rounded-lg text-[var(--phosphor-dim)] transition hover:bg-[var(--ui-hover)] hover:text-[var(--phosphor)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ui-accent)]"
          aria-label="Close settings"
        >
          <X className="h-4 w-4" />
        </button>

        <div className="settings-dialog-layout min-h-0 flex-1">
          <aside className="panel-rail settings-nav-rail" aria-label="Settings sections">
            <div className="panel-rail__inner">
              <div className="panel-rail__header settings-nav-rail__header">
                <h2
                  id="settings-title"
                  className="px-2.5 pb-[18px] text-[17px] font-semibold text-[var(--phosphor-bright)]"
                >
                  Settings
                </h2>
              </div>
              <nav className="panel-rail__groups settings-nav-groups">
                {NAV_GROUPS.map((group) => (
                  <div key={group.label} className="panel-rail__group">
                    <div className="panel-rail__eyebrow type-eyebrow">{group.label}</div>
                    <ul className="panel-rail__list">
                      {group.tabs.map((tabId) => {
                        const meta = TAB_META[tabId];
                        const Icon = meta.icon;
                        const isActive = tab === tabId;
                        return (
                          <li key={tabId}>
                            <button
                              type="button"
                              onClick={() => setTab(tabId)}
                              aria-current={isActive ? 'page' : undefined}
                              data-active={isActive ? 'true' : 'false'}
                              className="panel-rail__item"
                            >
                              <Icon className="panel-rail__item-icon h-4 w-4" aria-hidden />
                              <span className="panel-rail__item-label truncate">{meta.label}</span>
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                ))}
              </nav>
            </div>
          </aside>

          <div className="settings-content-panel min-h-0 min-w-0 flex-1">
            <header className="settings-content-header">
              <h3 className="font-display text-lg font-semibold tracking-tight text-[var(--phosphor-bright)]">
                {activeMeta.label}
              </h3>
              <p className="mt-1 max-w-xl text-sm leading-relaxed text-[var(--phosphor-dim)]">
                {activeMeta.description}
              </p>
            </header>

            <div className="settings-content-body">
              {error ? (
                <div className="mb-4 rounded-lg border border-[rgba(239,68,68,0.35)] bg-[rgba(239,68,68,0.1)] px-3 py-2 text-xs text-[#f87171]">
                  {error}
                </div>
              ) : null}

              {tab === 'profile' && (
                <ProfilePanel user={user} authConfig={authConfig} onAccountDeleted={onAccountDeleted} />
              )}

              {tab === 'appearance' && <AppearancePanel theme={theme} onSetTheme={onSetTheme} />}

              {tab === 'permissions' && (
                <section className="grid gap-2.5" role="radiogroup" aria-label="Tool permission mode">
                  {PERMISSION_OPTIONS.map((option) => {
                    const selected = toolPermissionMode === option.value;
                    return (
                      <button
                        key={option.value}
                        type="button"
                        role="radio"
                        aria-checked={selected}
                        data-selected={selected ? 'true' : 'false'}
                        onClick={() => onToolPermissionModeChange(option.value)}
                        className="perm-card w-full text-left"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="text-sm font-medium text-[var(--phosphor-bright)]">{option.label}</div>
                            <div className="mt-0.5 text-[11px] leading-relaxed text-[var(--phosphor-dim)]">
                              {option.hint}
                            </div>
                          </div>
                          {selected ? (
                            <CheckCircle2
                              className="perm-card-indicator h-4 w-4 shrink-0 text-[var(--ui-accent)]"
                              aria-hidden
                            />
                          ) : (
                            <Circle
                              className="perm-card-indicator h-4 w-4 shrink-0 text-[var(--phosphor-dim)] opacity-50"
                              aria-hidden
                            />
                          )}
                        </div>
                      </button>
                    );
                  })}
                </section>
              )}

              {tab === 'mcp' && (
                <section className="space-y-3">
                  {loading && servers.length === 0 ? (
                    <div className="text-xs text-[var(--phosphor-dim)]">Loading…</div>
                  ) : null}
                  {servers.map((server) => (
                    <div
                      key={server.id}
                      className="rounded-xl border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] px-3 py-2.5"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="truncate text-sm font-medium text-[var(--phosphor-bright)]">
                            {server.name}
                          </div>
                          <div className="truncate text-[11px] text-[var(--phosphor-dim)]">{server.url}</div>
                        </div>
                        <div className="flex shrink-0 gap-1">
                          <button
                            type="button"
                            onClick={() =>
                              void (async () => {
                                setTestingId(server.id);
                                try {
                                  await testMcpServer(server.id);
                                  await refreshTab('mcp');
                                } catch (e) {
                                  setError(e instanceof Error ? e.message : 'Test failed');
                                } finally {
                                  setTestingId(null);
                                }
                              })()
                            }
                            className="rounded-lg border border-[var(--ui-border)] px-2 py-1 text-[10px]"
                          >
                            {testingId === server.id ? '…' : 'Test'}
                          </button>
                          <button
                            type="button"
                            onClick={() => void deleteMcpServer(server.id).then(() => refreshTab('mcp'))}
                            className="rounded-lg border border-[var(--ui-border)] p-1"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                  <div className="space-y-2 rounded-xl border border-dashed border-[var(--ui-border)] p-3">
                    <div className="flex items-center gap-1.5 text-[11px] font-medium text-[var(--phosphor-dim)]">
                      <Zap className="h-3.5 w-3.5" /> Add MCP server
                    </div>
                    <input
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="Name"
                      className="w-full rounded-lg border border-[var(--ui-border)] bg-[var(--ui-bg)] px-3 py-2 text-sm"
                    />
                    <input
                      value={url}
                      onChange={(e) => setUrl(e.target.value)}
                      placeholder="https://…/mcp"
                      className="w-full rounded-lg border border-[var(--ui-border)] bg-[var(--ui-bg)] px-3 py-2 text-sm"
                    />
                    <input
                      value={authHeader}
                      onChange={(e) => setAuthHeader(e.target.value)}
                      placeholder="Authorization token"
                      className="w-full rounded-lg border border-[var(--ui-border)] bg-[var(--ui-bg)] px-3 py-2 text-sm"
                    />
                    <button type="button" onClick={() => void handleAddMcp()} className="settings-accent-btn">
                      Add server
                    </button>
                  </div>
                </section>
              )}

              {tab === 'skills' && (
                <section className="space-y-2">
                  {loading && skills.length === 0 ? (
                    <div className="text-xs text-[var(--phosphor-dim)]">Loading…</div>
                  ) : null}
                  {skills.map((skill) => (
                    <div
                      key={skill.id}
                      className="rounded-xl border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] px-3 py-2.5"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <div className="text-sm font-medium text-[var(--phosphor-bright)]">
                            {skill.name}
                            {skill.bundled ? (
                              <span className="ml-2 text-[10px] text-[var(--phosphor-dim)]">bundled</span>
                            ) : null}
                          </div>
                          <div className="text-[11px] text-[var(--phosphor-dim)]">
                            {skill.description || skill.id}
                          </div>
                          {skill.triggers.length > 0 ? (
                            <div className="mt-1 text-[10px] text-[var(--phosphor-dim)]">
                              Triggers: {skill.triggers.join(', ')}
                            </div>
                          ) : null}
                        </div>
                        <button
                          type="button"
                          onClick={() =>
                            void updateSkill(skill.id, { enabled: !skill.enabled }).then(() => refreshTab('skills'))
                          }
                          className={clsx(
                            'rounded-lg border px-2 py-1 text-[10px]',
                            skill.enabled
                              ? 'border-emerald-500/30 text-emerald-400'
                              : 'border-[var(--ui-border)] text-[var(--phosphor-dim)]',
                          )}
                        >
                          {skill.enabled ? 'On' : 'Off'}
                        </button>
                      </div>
                    </div>
                  ))}
                  <p className="text-[11px] text-[var(--phosphor-dim)]">
                    Try <code className="rounded bg-[var(--ui-bg)] px-1">/live-brief</code> or say &quot;morning
                    briefing&quot;.
                  </p>
                </section>
              )}

              {tab === 'assistants' && <AssistantsPanel open={open} />}

              {tab === 'tasks' && (
                <section className="space-y-2">
                  {loading && tasks.length === 0 ? (
                    <div className="text-xs text-[var(--phosphor-dim)]">No tasks yet.</div>
                  ) : null}
                  {tasks.map((task) => (
                    <div
                      key={task.id}
                      className="rounded-xl border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] px-3 py-2.5"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <div className="text-sm font-medium text-[var(--phosphor-bright)]">{task.title}</div>
                          <div className="text-[11px] text-[var(--phosphor-dim)]">{task.detail || task.source}</div>
                        </div>
                        <div className="flex shrink-0 gap-1">
                          {task.status !== 'completed' ? (
                            <button
                              type="button"
                              onClick={() =>
                                void updateAgentTaskStatus(task.id, 'completed').then(() => refreshTab('tasks'))
                              }
                              className="rounded-lg border border-[var(--ui-border)] p-1"
                              aria-label="Complete task"
                            >
                              <CheckCircle2 className="h-3.5 w-3.5" />
                            </button>
                          ) : null}
                          <button
                            type="button"
                            onClick={() => void deleteAgentTask(task.id).then(() => refreshTab('tasks'))}
                            className="rounded-lg border border-[var(--ui-border)] p-1"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </section>
              )}

              {tab === 'diagnostics' && (
                <section className="space-y-3">
                  {loading && !doctor ? (
                    <div className="text-sm text-[var(--phosphor-dim)]">Running checks…</div>
                  ) : null}
                  {!loading && !doctor && !error ? (
                    <div className="text-sm text-[var(--phosphor-dim)]">No diagnostics data available.</div>
                  ) : null}
                  {doctor ? (
                    <>
                      <div className="doctor-status" data-status={doctor.status}>
                        Status: {doctor.status}
                      </div>
                      {doctor.issues.length > 0 ? (
                        <ul className="space-y-1 text-sm text-[var(--phosphor-dim)]">
                          {doctor.issues.map((issue) => (
                            <li key={issue}>• {issue}</li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-sm text-[var(--phosphor-dim)]">No issues detected.</p>
                      )}
                      <div className="rounded-xl border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] p-3">
                        <pre className="doctor-report-json overflow-x-auto whitespace-pre-wrap">
                          {JSON.stringify(doctor.checks, null, 2)}
                        </pre>
                      </div>
                    </>
                  ) : null}
                </section>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
