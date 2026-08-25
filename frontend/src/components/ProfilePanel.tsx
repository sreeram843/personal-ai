import { useState } from 'react';
import type { AuthConfig, CurrentUser } from '../api';
import { deleteAccount, exportAccountData } from '../api';
import { userInitials, userLabel } from '../utils/userDisplay';
import { ConfirmDialog } from './ConfirmDialog';

interface Props {
  user: CurrentUser;
  authConfig: AuthConfig;
  onAccountDeleted?: () => void;
}

function signInMethodLabel(authConfig: AuthConfig): string {
  if (authConfig.auth_disabled) {
    return 'Development mode';
  }
  if (authConfig.google_auth_enabled) {
    return 'Google';
  }
  return 'Email';
}

export function ProfilePanel({ user, authConfig, onAccountDeleted }: Props) {
  const name = userLabel(user);
  const email = user.email?.trim() || 'No email on file';
  const [busy, setBusy] = useState<'export' | 'delete' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const handleExport = async () => {
    setBusy('export');
    setError(null);
    try {
      const payload = await exportAccountData();
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `curai-export-${user.id.slice(0, 8)}.json`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed');
    } finally {
      setBusy(null);
    }
  };

  const handleDelete = async () => {
    setBusy('delete');
    setError(null);
    try {
      await deleteAccount();
      setConfirmDelete(false);
      onAccountDeleted?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed');
      setBusy(null);
    }
  };

  return (
    <section className="space-y-5">
      <div className="flex items-center gap-3.5 rounded-[10px] bg-[var(--ui-bg-elevated)] px-[18px] py-4">
        <div className="grid h-[42px] w-[42px] shrink-0 place-content-center rounded-full bg-[var(--ui-accent)] text-sm font-bold text-[var(--ui-accent-fg)]">
          {userInitials(user)}
        </div>
        <div className="min-w-0">
          <div className="truncate text-[14.5px] font-semibold text-[var(--phosphor-bright)]">
            {name}
          </div>
          <div className="truncate text-[12.5px] text-[var(--ui-text-secondary)]">{email}</div>
        </div>
      </div>

      <dl className="space-y-4">
        <div>
          <dt className="type-eyebrow mb-1.5">Display name</dt>
          <dd className="text-sm text-[var(--phosphor)]">{user.display_name?.trim() || name}</dd>
        </div>
        <div>
          <dt className="type-eyebrow mb-1.5">Email</dt>
          <dd className="text-sm text-[var(--phosphor)]">{email}</dd>
        </div>
        <div>
          <dt className="type-eyebrow mb-1.5">Sign-in method</dt>
          <dd className="text-sm text-[var(--phosphor)]">{signInMethodLabel(authConfig)}</dd>
        </div>
        <div>
          <dt className="type-eyebrow mb-1.5">User ID</dt>
          <dd className="type-meta break-all text-[var(--phosphor-dim)]">{user.id}</dd>
        </div>
      </dl>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => {
            void handleExport();
          }}
          disabled={busy !== null}
          className="rounded-lg border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] px-3 py-2 text-sm text-[var(--phosphor)] transition hover:border-[var(--ui-accent)] disabled:opacity-60"
        >
          {busy === 'export' ? 'Exporting…' : 'Export conversations'}
        </button>
        {!authConfig.auth_disabled && (
          <button
            type="button"
            onClick={() => setConfirmDelete(true)}
            disabled={busy !== null}
            className="rounded-lg border border-[rgba(239,68,68,0.35)] px-3 py-2 text-sm text-[#f87171] transition hover:bg-[rgba(239,68,68,0.1)] disabled:opacity-60"
          >
            Delete account
          </button>
        )}
      </div>

      {error && (
        <p className="rounded-lg border border-[rgba(239,68,68,0.35)] bg-[rgba(239,68,68,0.1)] px-3 py-2 text-sm text-[#f87171]">
          {error}
        </p>
      )}

      <p className="text-xs leading-relaxed text-[var(--phosphor-dim)]">
        Account details come from your sign-in provider. Conversations and uploads are private to this account.
        Export downloads JSON. Delete permanently removes your conversations, documents, and vectors.
      </p>

      <ConfirmDialog
        open={confirmDelete}
        title="Delete account?"
        message="This permanently deletes your CurieAI account, conversations, and uploaded documents. This cannot be undone."
        confirmLabel={busy === 'delete' ? 'Deleting…' : 'Delete account'}
        tone="danger"
        loading={busy === 'delete'}
        onCancel={() => {
          if (busy !== 'delete') {
            setConfirmDelete(false);
          }
        }}
        onConfirm={() => {
          void handleDelete();
        }}
      />
    </section>
  );
}
