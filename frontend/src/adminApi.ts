import { apiFetch } from './api';

export interface AdminUserRow {
  id: string;
  email?: string | null;
  display_name?: string | null;
  role: string;
  is_active: boolean;
  created_at?: string | null;
  last_login_at?: string | null;
  conversation_count: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface AdminInvite {
  id: string;
  email: string;
  role: string;
  token: string;
  expires_at: string;
  accepted_at?: string | null;
  invite_url?: string | null;
}

export interface AdminProvider {
  id: string;
  name: string;
  display_name: string;
  base_url: string;
  enabled: boolean;
  has_key: boolean;
  key_last4?: string | null;
}

export interface AdminRouting {
  default_provider: string;
  default_model: string;
  planner_provider: string;
  planner_model: string;
  synthesizer_provider: string;
  synthesizer_model: string;
  reviewer_provider: string;
  reviewer_model: string;
  writer_provider: string;
  writer_model: string;
}

export interface AdminUsageSummary {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  series: Array<{ date: string; prompt_tokens: number; completion_tokens: number; total_tokens: number }>;
  by_model: Array<{ model: string; total_tokens: number }>;
}

export interface AdminUsageByUser {
  user_id?: string | null;
  email?: string | null;
  display_name?: string | null;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return (await response.json()) as T;
}

export async function fetchAdminMe() {
  return readJson<{ id: string; email?: string | null; display_name?: string | null; role: string; is_admin: boolean }>(
    await apiFetch('/admin/me'),
  );
}

export async function fetchAdminUsers(q?: string) {
  const query = q ? `?q=${encodeURIComponent(q)}` : '';
  return readJson<AdminUserRow[]>(await apiFetch(`/admin/users${query}`));
}

export async function updateAdminUser(userId: string, body: { role?: string; is_active?: boolean }) {
  return readJson<AdminUserRow>(
    await apiFetch(`/admin/users/${userId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  );
}

export async function fetchAdminInvites() {
  return readJson<AdminInvite[]>(await apiFetch('/admin/invites'));
}

export async function createAdminInvite(body: { email: string; role?: string }) {
  return readJson<AdminInvite>(
    await apiFetch('/admin/invites', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  );
}

export async function fetchAdminProviders() {
  return readJson<AdminProvider[]>(await apiFetch('/admin/providers'));
}

export async function createAdminProvider(body: {
  name: string;
  display_name: string;
  base_url: string;
  api_key?: string;
  enabled?: boolean;
}) {
  return readJson<AdminProvider>(
    await apiFetch('/admin/providers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  );
}

export async function updateAdminProvider(
  id: string,
  body: { display_name?: string; base_url?: string; api_key?: string; enabled?: boolean },
) {
  return readJson<AdminProvider>(
    await apiFetch(`/admin/providers/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  );
}

export async function fetchAdminRouting() {
  return readJson<AdminRouting>(await apiFetch('/admin/routing'));
}

export async function updateAdminRouting(body: AdminRouting) {
  return readJson<AdminRouting>(
    await apiFetch('/admin/routing', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  );
}

export async function fetchAdminSignupMode() {
  return readJson<{ mode: string }>(await apiFetch('/admin/signup-mode'));
}

export async function updateAdminSignupMode(mode: string) {
  return readJson<{ mode: string }>(
    await apiFetch('/admin/signup-mode', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode }),
    }),
  );
}

export async function fetchAdminUsageSummary(days = 30) {
  return readJson<AdminUsageSummary>(await apiFetch(`/admin/usage/summary?days=${days}`));
}

export async function fetchAdminUsageByUser(days = 30) {
  return readJson<AdminUsageByUser[]>(await apiFetch(`/admin/usage/by-user?days=${days}`));
}
