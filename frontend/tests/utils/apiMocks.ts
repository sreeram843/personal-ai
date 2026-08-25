import type { Page } from '@playwright/test';

const nowIso = () => new Date().toISOString();

type FetchStub = {
  method: string;
  pathEquals?: string;
  pathIncludes?: string;
  status?: number;
  contentType?: string;
  body: string;
};

const fetchStubsByPage = new WeakMap<Page, FetchStub[]>();

function queueFetchStub(page: Page, stub: FetchStub): void {
  const stubs = fetchStubsByPage.get(page) ?? [];
  stubs.push(stub);
  fetchStubsByPage.set(page, stubs);
}

/**
 * Linux WebKit often skips Playwright page.route for fetch POSTs (JSON and
 * multipart). In-page fetch stubs still run because they wrap window.fetch.
 */
async function installQueuedFetchStubs(page: Page): Promise<void> {
  const stubs = fetchStubsByPage.get(page) ?? [];
  await page.addInitScript((installed: FetchStub[]) => {
    const originalFetch = window.fetch.bind(window);
    window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      const raw =
        typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
      let pathname = raw;
      try {
        pathname = new URL(raw, window.location.origin).pathname;
      } catch {
        /* keep raw */
      }
      const method = (init?.method ?? (input instanceof Request ? input.method : 'GET')).toUpperCase();
      for (let index = installed.length - 1; index >= 0; index -= 1) {
        const stub = installed[index];
        if (stub.method !== method) {
          continue;
        }
        if (stub.pathEquals && pathname !== stub.pathEquals) {
          continue;
        }
        if (stub.pathIncludes && !pathname.includes(stub.pathIncludes)) {
          continue;
        }
        if (!stub.pathEquals && !stub.pathIncludes) {
          continue;
        }
        return new Response(stub.body, {
          status: stub.status ?? 200,
          headers: { 'Content-Type': stub.contentType ?? 'application/json' },
        });
      }
      return originalFetch(input, init);
    };
  }, stubs);
}

export async function mockIngestFiles(
  page: Page,
  payload: { count?: number; job_id?: string; status?: string } = { count: 1 },
): Promise<void> {
  const body = JSON.stringify(payload);
  queueFetchStub(page, {
    method: 'POST',
    pathEquals: '/ingest/files',
    body,
  });
  await page.route('**/ingest/files', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body,
    });
  });
}

export async function mockSseStream(page: Page, path: '/chat/stream' | '/smart_chat/stream', body: string): Promise<void> {
  queueFetchStub(page, {
    method: 'POST',
    pathEquals: path,
    contentType: 'text/event-stream',
    body,
  });
  await page.route(`**${path}`, async (route) => {
    if (route.request().method() !== 'POST') {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body,
    });
  });
}

export async function installApiBootstrapMocks(page: Page): Promise<void> {
  const authConfig = JSON.stringify({
    auth_disabled: true,
    google_client_id: null,
    google_auth_enabled: false,
    support_email: 'hello@cura-i.com',
  });
  const tokenBody = JSON.stringify({
    access_token: 'playwright-test-token',
    token_type: 'bearer',
    user_id: '00000000-0000-0000-0000-000000000001',
  });
  const meBody = JSON.stringify({
    id: '00000000-0000-0000-0000-000000000001',
    email: 'dev@localhost',
    display_name: 'Dev User',
  });
  const assistantsBody = JSON.stringify({
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
  });
  const conversationsListBody = JSON.stringify({ conversations: [] });
  const createdConversationBody = JSON.stringify({
    id: 'new-conversation-id',
    title: 'New conversation',
    mode: 'smart',
    message_count: 0,
    created_at: nowIso(),
    updated_at: nowIso(),
  });
  const emptyMessagesBody = JSON.stringify({
    conversation_id: 'new-conversation-id',
    messages: [],
  });

  queueFetchStub(page, { method: 'GET', pathEquals: '/auth/config', body: authConfig });
  queueFetchStub(page, { method: 'POST', pathEquals: '/auth/logout', status: 204, body: '' });
  queueFetchStub(page, { method: 'POST', pathEquals: '/auth/token', body: tokenBody });
  queueFetchStub(page, { method: 'GET', pathEquals: '/auth/me', body: meBody });
  queueFetchStub(page, { method: 'GET', pathEquals: '/agent/assistants', body: assistantsBody });
  queueFetchStub(page, { method: 'GET', pathEquals: '/conversations', body: conversationsListBody });
  queueFetchStub(page, {
    method: 'POST',
    pathEquals: '/conversations',
    status: 201,
    body: createdConversationBody,
  });
  queueFetchStub(page, {
    method: 'GET',
    pathEquals: '/conversations/new-conversation-id/messages',
    body: emptyMessagesBody,
  });
  queueFetchStub(page, { method: 'DELETE', pathIncludes: '/conversations/', status: 204, body: '' });

  await page.route('**/auth/config', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: authConfig,
    });
  });

  await page.route('**/auth/logout', async (route) => {
    await route.fulfill({ status: 204, body: '' });
  });

  await page.route('**/auth/token', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: tokenBody,
    });
  });

  await page.route('**/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: meBody,
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
      body: assistantsBody,
    });
  });

  await page.route('**/conversations', async (route) => {
    const method = route.request().method();

    if (method === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: conversationsListBody,
      });
      return;
    }

    if (method === 'POST') {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: createdConversationBody,
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
      body: emptyMessagesBody,
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
  const body = JSON.stringify({
    conversation_id: conversationId,
    messages: messages.map((message) => ({
      ...message,
      created_at: nowIso(),
    })),
  });
  queueFetchStub(page, {
    method: 'GET',
    pathEquals: `/conversations/${conversationId}/messages`,
    body,
  });
  await page.route(`**/conversations/${conversationId}/messages`, async (route) => {
    if (route.request().method() !== 'GET') {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body,
    });
  });
}

export async function prepareAuthenticatedPage(
  page: Page,
  options: {
    mode?: 'chat' | 'smart';
    conversations?: Array<{
      id: string;
      title: string;
      mode?: string;
      message_count?: number;
      pinned?: boolean;
    }>;
  } = {},
): Promise<void> {
  await installApiBootstrapMocks(page);
  if (options.conversations) {
    const conversations = options.conversations;
    const now = nowIso();
    const listBody = JSON.stringify({
      conversations: conversations.map((conversation) => ({
        id: conversation.id,
        title: conversation.title,
        mode: conversation.mode ?? 'smart',
        message_count: conversation.message_count ?? 0,
        pinned: conversation.pinned ?? false,
        created_at: now,
        updated_at: now,
      })),
    });
    queueFetchStub(page, { method: 'GET', pathEquals: '/conversations', body: listBody });
    await page.route('**/conversations', async (route) => {
      if (route.request().method() !== 'GET') {
        await route.fallback();
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: listBody,
      });
    });
  }
  await page.addInitScript(({ mode }) => {
    localStorage.clear();
    localStorage.setItem('personal-ai-auth-token', 'playwright-test-token');
    if (mode) {
      localStorage.setItem('personal-ai-mode', JSON.stringify(mode));
    }
  }, { mode: options.mode });
  await installQueuedFetchStubs(page);
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  const readyText =
    options.mode === 'chat' ? 'Start a direct model conversation' : 'Start a smart-routed conversation';
  await page.getByRole('main').waitFor({ state: 'visible', timeout: 15000 });
  await page.getByText(readyText).waitFor({ state: 'visible', timeout: 15000 });
}
