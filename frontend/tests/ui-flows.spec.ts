import { expect, test } from '@playwright/test';
import { assertQaGuards, installQaGuards } from './utils/qaGuards';

async function preparePage(page: import('@playwright/test').Page) {
  await page.goto('/');
  await page.evaluate(() => {
    localStorage.clear();
  });
  await page.goto('/');
}

test.describe('browser interaction flows', () => {
  test.beforeEach(async ({ page }) => {
    installQaGuards(page);
  });

  test.afterEach(async ({ page }) => {
    await assertQaGuards(page);
  });

  test('classic quick chat sends a prompt and new chat clears history', async ({ page }) => {
    await page.route('**/chat', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          message: '[12:00:00] MACHINE_ALPHA_7: > CACHE PIPELINE VERIFIED',
        }),
      });
    });

    await preparePage(page);
    await page.getByRole('button', { name: 'QUICK CHAT', exact: true }).click();
    await page.getByPlaceholder('Ask a follow-up...').fill('Explain the cache path');
    await page.getByRole('button', { name: 'Send' }).click();

    await expect(page.getByRole('log').getByText('Explain the cache path', { exact: true })).toBeVisible();
    await expect(page.getByText('CACHE PIPELINE VERIFIED')).toBeVisible();

    await page.getByRole('button', { name: 'Start new conversation' }).click();
    await expect(page.getByText('Start a direct model conversation')).toBeVisible();
    await expect(page.getByText('CACHE PIPELINE VERIFIED')).not.toBeVisible();
  });

  test('smart flow renders returned citations', async ({ page }) => {
    await page.route('**/smart_chat/stream', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: `data: ${JSON.stringify({
          type: 'final',
          response: {
            message: '[12:00:00] MACHINE_ALPHA_7: > SMART RESPONSE READY',
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
    await page.getByPlaceholder('Ask a follow-up...').fill('Summarize the ops guidance');
    await page.getByRole('button', { name: 'Send' }).click();

    await expect(page.getByText('SMART RESPONSE READY')).toBeVisible();
    await expect(page.getByText('SOURCES', { exact: true })).toBeVisible();
    await expect(page.getByText('ops-runbook.md', { exact: true })).toBeVisible();
    await expect(page.getByText('docs/ops-runbook.md')).toBeVisible();
  });

  test('document upload shows a success status', async ({ page }) => {
    await page.route('**/ingest', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ count: 1 }),
      });
    });

    await preparePage(page);
    await page.getByRole('button', { name: 'Upload documents' }).click();
    await page.locator('input[type="file"]').setInputFiles({
      name: 'sample-notes.md',
      mimeType: 'text/markdown',
      buffer: Buffer.from('# Sample\n\nThis file is used for Playwright upload coverage.\n', 'utf-8'),
    });

    await expect(page.getByText('sample-notes.md')).toBeVisible();
    await expect(page.getByText('SUCCESS')).toBeVisible();
  });

  test('terminal mode toggle persists after reload', async ({ page }) => {
    await preparePage(page);
    await page.getByRole('button', { name: 'Open user settings' }).first().click();
    await page.getByRole('button', { name: 'Terminal' }).click();
    await expect(page.getByText('CHAT MODE ONLY')).toBeVisible();

    await page.reload();
    await expect(page.getByText('CHAT MODE ONLY')).toBeVisible();
  });
});