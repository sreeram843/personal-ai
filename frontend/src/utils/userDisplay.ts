import type { CurrentUser } from '../api';

export function userInitials(user: CurrentUser): string {
  const name = (user.display_name || '').trim();
  if (name) {
    const parts = name.split(/\s+/).filter(Boolean);
    if (parts.length >= 2) {
      return `${parts[0][0] ?? ''}${parts[1][0] ?? ''}`.toUpperCase();
    }
    return name.slice(0, 2).toUpperCase();
  }

  const email = (user.email || '').trim();
  if (email) {
    return email.slice(0, 2).toUpperCase();
  }

  return 'U';
}

export function userLabel(user: CurrentUser): string {
  return user.display_name?.trim() || user.email?.trim() || 'Signed in';
}
