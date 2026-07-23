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

  await page.route('**/agent/assistants', async (route) => {
    if (route.request().method() !== 'GET') {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        assistants: [
          {
            id: 'default',
            name: 'Default',
            description: 'Playwright default assistant',
            triggers: [],
            allowed_tools: [],
            enabled: true,
            bundled: true,
            pick_only: false,
            is_default: true,
          },
        ],
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

  await page.route('**/conversations/new-conversation-id/messages', async (route) => {
    if (route.request().method() !== 'GET') {
      await route.continue();
      return;
    }
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

export async function mockConversationMessages(
  page: Page,
  conversationId: string,
  messages: Array<{
    id: string;
    role: 'user' | 'assistant';
    content: string;
    metadata?: Record<string, unknown>;
  }>,
): Promise<void> {
  await page.route(`**/conversations/${conversationId}/messages`, async (route) => {
    if (route.request().method() !== 'GET') {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        conversation_id: conversationId,
        messages: messages.map((message) => ({
          ...message,
          created_at: nowIso(),
        })),
      }),
    });
  });
}

export async function prepareAuthenticatedPage(page: Page): Promise<void> {
  await installApiBootstrapMocks(page);
  await page.addInitScript(() => {
    localStorage.clear();
    localStorage.setItem('personal-ai-auth-token', 'playwright-test-token');
  });
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await page.getByText('What can I help with?').waitFor({ state: 'visible', timeout: 15000 });
}
