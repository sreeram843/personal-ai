import { clsx } from 'clsx';
import { ChevronLeft, ChevronRight, FileUp, MessageCirclePlus, MessageSquare, Settings, Sparkles, X } from 'lucide-react';
import type { ConversationMode, PersonaType } from '../types';

interface ConversationSummary {
  id: string;
  title: string;
  updatedAt?: number;
  messageCount: number;
}

interface Props {
  mode: ConversationMode;
  onModeChange: (mode: ConversationMode) => void;
  onNewChat: () => void;
  onUpload: () => void;
  theme: 'light' | 'dark';
  onSetTheme: (theme: 'light' | 'dark') => void;
  onSetUiMode: (mode: 'classic' | 'terminal') => void;
  phosphor: 'green' | 'amber';
  onSetPhosphor: (phosphor: 'green' | 'amber') => void;
  persona: import('../types').PersonaType;
  onPersonaChange: (persona: import('../types').PersonaType) => void;
  conversations: ConversationSummary[];
  activeConversationId: string;
  onSelectConversation: (id: string) => void;
  uiMode: 'classic' | 'terminal';
  sidebarCollapsed: boolean;
  onToggleSidebarCollapsed: () => void;
  settingsOpen: boolean;
  onOpenSettings: () => void;
  onCloseSettings: () => void;
}

export function Sidebar({
  mode,
  onModeChange,
  onNewChat,
  onUpload,
  theme,
  onSetTheme,
  onSetUiMode,
  phosphor,
  onSetPhosphor,
  persona,
  onPersonaChange,
  conversations,
  activeConversationId,
  onSelectConversation,
  uiMode,
  sidebarCollapsed,
  onToggleSidebarCollapsed,
  settingsOpen,
  onOpenSettings,
  onCloseSettings,
}: Props) {
  const isTerminalUI = uiMode === 'terminal';
  const iconButtonBase =
    'grid h-10 w-10 shrink-0 place-content-center rounded-lg border border-[var(--ui-border)] text-[var(--phosphor)] transition hover:bg-[var(--ui-bg-elevated)] focus-visible:ring-2 focus-visible:ring-[var(--ui-focus)]';

  const menus = [
    {
      id: 'chat',
      label: 'QUICK CHAT',
      icon: MessageSquare,
      description: 'FAST DIRECT RESPONSES',
    },
    {
      id: 'smart',
      label: 'SMART CHAT',
      icon: Sparkles,
      description: 'AUTO-ROUTES CHAT/RAG/WORKFLOW',
    },
  ] as const;

  const personas = [
    { id: 'ideal_chatbot', label: 'IDEAL CHATBOT', description: 'Principled Assistant' },
    { id: 'therapist', label: 'THERAPIST', description: 'Empathetic & Validating' },
    { id: 'barney', label: 'BARNEY', description: 'Charismatic Mentor' },
  ] as const;

  const settingsPanel = settingsOpen ? (
    <div className="absolute inset-0 z-20 flex items-start justify-end bg-black/30 p-2 md:p-3">
      <div className="w-full max-w-xs rounded-xl border border-[var(--ui-border-strong)] bg-[var(--ui-panel-strong)] p-3 shadow-xl">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <div className="text-xs uppercase tracking-[0.28em] text-[var(--phosphor-dim)]">User Settings</div>
            <div className="text-sm font-semibold text-[var(--phosphor-bright)]">Interface Controls</div>
          </div>
          <button
            type="button"
            onClick={onCloseSettings}
            className="grid h-8 w-8 place-content-center rounded border border-[var(--ui-border)] transition hover:bg-[var(--ui-bg-elevated)]"
            aria-label="Close user settings"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-3">
          <div>
            <div className="mb-1 text-[10px] uppercase tracking-[0.18em] text-[var(--phosphor-dim)]">Theme</div>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => onSetTheme('light')}
                className={clsx(
                  'rounded border px-2 py-1.5 text-xs transition',
                  theme === 'light'
                    ? 'border-[var(--ui-border-strong)] bg-[var(--ui-bg-elevated)] text-[var(--phosphor-bright)]'
                    : 'border-[var(--ui-border)] text-[var(--phosphor-dim)] hover:bg-[var(--ui-bg-elevated)]',
                )}
              >
                Light
              </button>
              <button
                type="button"
                onClick={() => onSetTheme('dark')}
                className={clsx(
                  'rounded border px-2 py-1.5 text-xs transition',
                  theme === 'dark'
                    ? 'border-[var(--ui-border-strong)] bg-[var(--ui-bg-elevated)] text-[var(--phosphor-bright)]'
                    : 'border-[var(--ui-border)] text-[var(--phosphor-dim)] hover:bg-[var(--ui-bg-elevated)]',
                )}
              >
                Dark
              </button>
            </div>
          </div>

          <div>
            <div className="mb-1 text-[10px] uppercase tracking-[0.18em] text-[var(--phosphor-dim)]">UI Mode</div>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => onSetUiMode('classic')}
                className={clsx(
                  'rounded border px-2 py-1.5 text-xs transition',
                  uiMode === 'classic'
                    ? 'border-[var(--ui-border-strong)] bg-[var(--ui-bg-elevated)] text-[var(--phosphor-bright)]'
                    : 'border-[var(--ui-border)] text-[var(--phosphor-dim)] hover:bg-[var(--ui-bg-elevated)]',
                )}
              >
                Classic
              </button>
              <button
                type="button"
                onClick={() => onSetUiMode('terminal')}
                className={clsx(
                  'rounded border px-2 py-1.5 text-xs transition',
                  uiMode === 'terminal'
                    ? 'border-[var(--ui-border-strong)] bg-[var(--ui-bg-elevated)] text-[var(--phosphor-bright)]'
                    : 'border-[var(--ui-border)] text-[var(--phosphor-dim)] hover:bg-[var(--ui-bg-elevated)]',
                )}
              >
                Terminal
              </button>
            </div>
          </div>

          <div>
            <div className="mb-1 text-[10px] uppercase tracking-[0.18em] text-[var(--phosphor-dim)]">Phosphor</div>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => onSetPhosphor('green')}
                className={clsx(
                  'rounded border px-2 py-1.5 text-xs transition',
                  phosphor === 'green'
                    ? 'border-[var(--ui-border-strong)] bg-[var(--ui-bg-elevated)] text-[var(--phosphor-bright)]'
                    : 'border-[var(--ui-border)] text-[var(--phosphor-dim)] hover:bg-[var(--ui-bg-elevated)]',
                )}
              >
                Green
              </button>
              <button
                type="button"
                onClick={() => onSetPhosphor('amber')}
                className={clsx(
                  'rounded border px-2 py-1.5 text-xs transition',
                  phosphor === 'amber'
                    ? 'border-[var(--ui-border-strong)] bg-[var(--ui-bg-elevated)] text-[var(--phosphor-bright)]'
                    : 'border-[var(--ui-border)] text-[var(--phosphor-dim)] hover:bg-[var(--ui-bg-elevated)]',
                )}
              >
                Amber
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  ) : null;

  if (isTerminalUI) {
    return (
      <aside className="relative flex border-b border-[var(--ui-border-strong)] bg-[var(--ui-panel-strong)] text-[var(--phosphor)] md:h-full md:w-[88px] md:min-w-[88px] md:flex-col md:border-b-0 md:border-r">
        <div className="flex w-full items-center justify-between px-3 py-3 md:flex-col md:justify-start md:gap-3 md:px-2 md:py-4">
          <div className="terminal-font text-[11px] tracking-[0.2em] text-[var(--phosphor-dim)] md:text-[10px]">TERM</div>
          <button
            type="button"
            onClick={() => onModeChange('chat')}
            aria-label="Chat mode"
            title="Chat mode"
            className="grid h-9 w-9 place-content-center rounded border border-[var(--ui-border-strong)] bg-[var(--ui-bg-elevated)] text-[var(--phosphor-bright)]"
          >
            <MessageSquare className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={onNewChat}
            title="New conversation"
            aria-label="Start new conversation"
            className={iconButtonBase}
          >
            <MessageCirclePlus className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={onUpload}
            title="Upload docs"
            aria-label="Upload documents"
            className={iconButtonBase}
          >
            <FileUp className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={onOpenSettings}
            title="User settings"
            aria-label="Open user settings"
            className={iconButtonBase}
          >
            <Settings className="h-4 w-4" />
          </button>
          <div className="hidden w-full border-t border-[var(--ui-border)] pt-2 text-center md:block">
            <div className="text-[10px] text-[var(--phosphor-dim)]">U1</div>
          </div>
        </div>
        {settingsPanel}
      </aside>
    );
  }

  return (
    <aside
      className={clsx(
        'relative flex border-b border-[var(--ui-border-strong)] bg-[color-mix(in_srgb,var(--ui-panel),transparent_2%)] text-[var(--phosphor)] transition-all duration-200 md:h-full md:flex-col md:border-b-0 md:border-r',
        sidebarCollapsed ? 'md:w-[74px] md:min-w-[74px]' : 'md:w-[280px] md:min-w-[280px]',
      )}
    >
      <div className="w-full px-3 py-3 md:px-4 md:py-4">
        <div className="mb-3 flex items-center gap-2">
          <div className="grid h-7 w-7 place-content-center rounded-md bg-[var(--ui-focus)] text-[var(--ui-bg)]">
            <Sparkles className="h-4 w-4" />
          </div>
          {!sidebarCollapsed && <div className="text-sm font-semibold text-[var(--phosphor-bright)]">Smart Chat</div>}
          <button
            type="button"
            onClick={onToggleSidebarCollapsed}
            className="ml-auto grid h-8 w-8 place-content-center rounded border border-[var(--ui-border)] text-[var(--phosphor)] transition hover:bg-[var(--ui-bg-elevated)]"
            title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {sidebarCollapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          </button>
        </div>

        <button
          type="button"
          onClick={onNewChat}
          title="New conversation"
          aria-label="Start new conversation"
          className="mb-3 flex w-full items-center gap-2 rounded-lg border border-[var(--ui-border)] bg-[var(--ui-panel-strong)] px-3 py-2 text-sm text-[var(--phosphor)] transition hover:bg-[var(--ui-bg-elevated)]"
        >
          <MessageCirclePlus className="h-4 w-4" />
          {!sidebarCollapsed && 'New conversation'}
        </button>

        {!sidebarCollapsed && (
          <>
            <div className="mb-2 text-[10px] uppercase tracking-[0.25em] text-[var(--phosphor-dim)]">Router</div>
            <div className="mb-3 grid grid-cols-2 gap-2">
              {menus.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onModeChange(item.id)}
                  title={`${item.label}: ${item.description}`}
                  aria-label={item.label}
                  className={clsx(
                    'rounded-md border px-2 py-1.5 text-xs font-medium transition',
                    mode === item.id
                      ? 'border-[var(--ui-border-strong)] bg-[var(--ui-bg-elevated)] text-[var(--phosphor-bright)]'
                      : 'border-[var(--ui-border)] text-[var(--phosphor-dim)] hover:bg-[var(--ui-bg-elevated)]',
                  )}
                >
                  {item.id === 'chat' ? <MessageSquare className="mr-1 inline h-3.5 w-3.5" /> : <Sparkles className="mr-1 inline h-3.5 w-3.5" />}
                  {item.id === 'chat' ? 'Chat' : 'Smart'}
                </button>
              ))}
            </div>

            <div className="mb-3">
              <select
                value={persona}
                onChange={(e) => onPersonaChange(e.target.value as PersonaType)}
                title="Select active persona"
                aria-label="Select persona"
                className={clsx(
                  'h-9 w-full rounded-lg border border-[var(--ui-border)] bg-[var(--ui-panel-strong)] text-[var(--phosphor)] transition',
                  'hover:bg-[var(--ui-bg-elevated)] focus:outline-none focus:ring-2 focus:ring-[var(--ui-focus)]',
                  'text-xs font-semibold cursor-pointer appearance-none px-2',
                )}
              >
                {personas.map((p) => (
                  <option key={p.id} value={p.id} className="bg-[var(--ui-panel)] text-[var(--phosphor)]">
                    {p.label}
                  </option>
                ))}
              </select>
            </div>
          </>
        )}

        {!sidebarCollapsed && <div className="mb-2 text-[10px] uppercase tracking-[0.25em] text-[var(--phosphor-dim)]">Recent</div>}
        <div className={clsx('space-y-1 overflow-y-auto pr-1', sidebarCollapsed ? 'max-h-[220px]' : 'max-h-[280px] md:max-h-[380px]')}>
          {conversations.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => onSelectConversation(item.id)}
              className={clsx(
                'w-full rounded-md px-2 py-2 text-left transition',
                item.id === activeConversationId
                  ? 'bg-[var(--ui-bg-elevated)] ring-1 ring-[var(--ui-border-strong)] shadow-[0_1px_0_rgba(24,95,165,0.06)]'
                  : 'hover:bg-[var(--ui-bg-elevated)]',
              )}
            >
              <div className="truncate text-xs font-medium text-[var(--phosphor)]">{sidebarCollapsed ? item.title.slice(0, 1) : item.title}</div>
              {!sidebarCollapsed && (
                <div className="mt-0.5 text-[10px] text-[var(--phosphor-dim)]">
                  {item.updatedAt ? new Date(item.updatedAt).toLocaleDateString() : 'Today'} · {item.messageCount} messages
                </div>
              )}
            </button>
          ))}
        </div>

        <div className="mt-3 flex items-center gap-2">
          <button
            type="button"
            onClick={onUpload}
            title="Upload docs"
            aria-label="Upload documents"
            className={iconButtonBase}
          >
            <FileUp className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={onOpenSettings}
            title="User settings"
            aria-label="Open user settings"
            className={iconButtonBase}
          >
            <Settings className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-4 flex items-center gap-2 border-t border-[var(--ui-border)] pt-3">
          <div className="grid h-8 w-8 place-content-center rounded-full bg-[var(--ui-bg-elevated)] text-[11px] font-semibold text-[var(--phosphor)]">U1</div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-xs font-semibold text-[var(--phosphor-bright)]">USER1</div>
            <div className="text-[10px] text-[var(--phosphor-dim)]">{theme === 'dark' ? 'Dark theme' : 'Light theme'}</div>
          </div>
          <span className="h-2 w-2 rounded-full bg-emerald-500" aria-hidden="true" />
        </div>
      </div>

      {settingsPanel}
    </aside>
  );
}
