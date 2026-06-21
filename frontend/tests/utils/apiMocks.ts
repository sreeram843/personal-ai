import type { Page } from '@playwright/test';

const nowIso = () => new Date().toISOString();

export async function installApiBootstrapMocks(page: Page): Promise<void> {
  await page.route('**/auth/config', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        auth_disabled: true,
        google_client_id: null,
        google_auth_enabled: false,
      }),
    });
  });

  await page.route('**/auth/token', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        access_token: 'playwright-test-token',
        token_type: 'bearer',
        user_id: '00000000-0000-0000-0000-000000000001',
      }),
    });
  });

  await page.route('**/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: '00000000-0000-0000-0000-000000000001',
        email: 'dev@localhost',
        display_name: 'Dev User',
      }),
    });
  });

  await page.route('**/conversations', async (route) => {
    const method = route.request().method();

    if (method === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ conversations: [] }),
      });
      return;
    }

    if (method === 'POST') {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'new-conversation-id',
          title: 'New conversation',
          mode: 'smart',
          message_count: 0,
          created_at: nowIso(),
          updated_at: nowIso(),
        }),
      });
      return;
    }

    await route.continue();
  });

  await page.route('**/conversations/*', async (route) => {
    const method = route.request().method();
    const url = route.request().url();
    const isMessages = url.includes('/messages');

    if (isMessages) {
      await route.continue();
      return;
    }

    if (method === 'PATCH') {
      const body = route.request().postDataJSON() as { title?: string; pinned?: boolean };
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'conv-1',
          title: body.title ?? 'Mock conversation',
          mode: 'smart',
          message_count: 0,
          pinned: body.pinned ?? false,
          pinned_at: body.pinned ? nowIso() : null,
          created_at: nowIso(),
          updated_at: nowIso(),
        }),
      });
      return;
    }

    if (method === 'DELETE') {
      await route.fulfill({ status: 204, body: '' });
      return;
    }

    await route.continue();
  });

  await page.route('**/conversations/*/messages', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        conversation_id: 'new-conversation-id',
        messages: [],
      }),
    });
  });
}
