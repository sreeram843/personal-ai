import type { AuthConfig, CurrentUser } from '../api';
import { userInitials, userLabel } from '../utils/userDisplay';

interface Props {
  user: CurrentUser;
  authConfig: AuthConfig;
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

export function ProfilePanel({ user, authConfig }: Props) {
  const name = userLabel(user);
  const email = user.email?.trim() || 'No email on file';

  return (
    <section className="space-y-5">
      <div className="flex items-center gap-4 rounded-xl border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] px-4 py-4">
        <div className="grid h-14 w-14 shrink-0 place-content-center rounded-full bg-[var(--ui-panel-strong)] text-base font-semibold text-[var(--phosphor-bright)]">
          {userInitials(user)}
        </div>
        <div className="min-w-0">
          <div className="truncate font-display text-lg font-semibold tracking-tight text-[var(--phosphor-bright)]">
            {name}
          </div>
          <div className="truncate text-sm text-[var(--phosphor-dim)]">{email}</div>
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

      <p className="text-xs leading-relaxed text-[var(--phosphor-dim)]">
        Account details come from your sign-in provider. Conversations and uploads are private to this account.
      </p>
    </section>
  );
}
