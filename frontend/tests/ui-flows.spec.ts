import { expect, test } from '@playwright/test';
import { prepareAuthenticatedPage, mockConversationMessages } from './utils/apiMocks';
import { assertQaGuards, installQaGuards } from './utils/qaGuards';

async function preparePage(page: import('@playwright/test').Page) {
  await prepareAuthenticatedPage(page);
}

test.describe('browser interaction flows', () => {
  test.beforeEach(async ({ page }) => {
    installQaGuards(page);
  });

  test.afterEach(async ({ page }) => {
    await assertQaGuards(page);
  });

  test('chat sends a prompt and new chat clears history', async ({ page }) => {
    await mockConversationMessages(page, 'conv-1', [
      { id: 'u1', role: 'user', content: 'Explain the cache path' },
      { id: 'a1', role: 'assistant', content: 'CACHE PIPELINE VERIFIED' },
    ]);

    await page.route('**/chat/stream', async (route) => {
      if (route.request().method() !== 'POST') {
        await route.continue();
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: [
          `data: ${JSON.stringify({ type: 'conversation', conversation_id: 'conv-1' })}`,
          `data: ${JSON.stringify({
            type: 'final',
            response: {
              message: 'CACHE PIPELINE VERIFIED',
              conversation_id: 'conv-1',
            },
          })}`,
        ].join('\n\n') + '\n\n',
      });
    });

    await preparePage(page);
    await page.getByPlaceholder(/Message/).fill('Explain the cache path');
    await page.getByRole('button', { name: 'Send message' }).click();

    await expect(page.getByRole('log').getByText('Explain the cache path', { exact: true })).toBeVisible();
    await expect(page.getByText('CACHE PIPELINE VERIFIED')).toBeVisible();

    await page.getByRole('button', { name: 'Start new conversation' }).click();
    await expect(page.getByText('Start a smart-routed conversation')).toBeVisible();
    await expect(page.getByText('CACHE PIPELINE VERIFIED')).not.toBeVisible();
  });

  test('chat flow returns assistant response without metadata panels', async ({ page }) => {
    await mockConversationMessages(page, 'conv-smart-1', [
      { id: 'u1', role: 'user', content: 'Summarize the ops guidance' },
      {
        id: 'a1',
        role: 'assistant',
        content: 'SMART RESPONSE READY',
        metadata: {
          sources: [
            {
              id: 'doc-1',
              score: 0.982,
              metadata: {
                name: 'ops-runbook.md',
                path: 'docs/ops-runbook.md',
              },
            },
          ],
        },
      },
    ]);

    await page.route('**/chat/stream', async (route) => {
      if (route.request().method() !== 'POST') {
        await route.continue();
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: `data: ${JSON.stringify({
          type: 'final',
          response: {
            message: 'SMART RESPONSE READY',
            conversation_id: 'conv-smart-1',
            sources: [
              {
                id: 'doc-1',
                score: 0.982,
                metadata: {
                  name: 'ops-runbook.md',
                  path: 'docs/ops-runbook.md',
                },
              },
            ],
          },
        })}\n\n`,
      });
    });

    await preparePage(page);
    await page.getByPlaceholder(/Message/).fill('Summarize the ops guidance');
    await page.getByRole('button', { name: 'Send message' }).click();

    await expect(page.getByText('SMART RESPONSE READY')).toBeVisible();
    await expect(page.getByText('ops-runbook.md')).not.toBeVisible();
  });

  test('workflow events stream without blocking the composer', async ({ page }) => {
    await page.route('**/chat/stream', async (route) => {
      if (route.request().method() !== 'POST') {
        await route.continue();
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: [
          `data: ${JSON.stringify({ type: 'workflow', event: 'plan', step_id: 'step_1', agent: 'planner' })}`,
          `data: ${JSON.stringify({
            type: 'final',
            response: {
              message: 'Workflow complete.',
              conversation_id: 'conv-workflow-1',
            },
          })}`,
        ].join('\n\n') + '\n\n',
      });
    });

    await preparePage(page);
    await page.getByPlaceholder(/Message/).fill('Plan a rollout strategy');
    await page.getByRole('button', { name: 'Send message' }).click();

    await expect(page.getByText('Workflow complete.')).toBeVisible();
    await expect(page.getByPlaceholder(/Message/)).toBeEnabled();
  });
});
