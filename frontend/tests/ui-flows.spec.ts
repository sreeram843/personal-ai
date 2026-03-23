import { expect, test } from '@playwright/test';

async function preparePage(page: import('@playwright/test').Page) {
  await page.goto('/');
  await page.evaluate(() => {
    localStorage.clear();
  });
  await page.goto('/');
}

test.describe('browser interaction flows', () => {
  test('classic standard chat sends a prompt and new chat clears history', async ({ page }) => {
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
    await page.getByRole('button', { name: 'STANDARD CHAT' }).click();
    await page.getByPlaceholder('> ENTER COMMAND').fill('Explain the cache path');
    await page.getByRole('button', { name: 'Send' }).click();

    await expect(page.getByText('Explain the cache path')).toBeVisible();
    await expect(page.getByText('CACHE PIPELINE VERIFIED')).toBeVisible();

    await page.getByRole('button', { name: 'Start new chat' }).click();
    await expect(page.getByText('Start a direct model conversation')).toBeVisible();
    await expect(page.getByText('CACHE PIPELINE VERIFIED')).not.toBeVisible();
  });

  test('rag flow renders returned citations', async ({ page }) => {
    await page.route('**/rag_chat', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          message: '[12:00:00] MACHINE_ALPHA_7: > RAG RESPONSE READY',
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
        }),
      });
    });

    await preparePage(page);
    await page.getByPlaceholder('> ENTER COMMAND').fill('Summarize the ops guidance');
    await page.getByRole('button', { name: 'Send' }).click();

    await expect(page.getByText('RAG RESPONSE READY')).toBeVisible();
    await expect(page.getByText('SOURCES')).toBeVisible();
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
    await page.getByRole('button', { name: 'Toggle UI mode' }).first().click();
    await expect(page.getByText('RAG MODE ONLINE')).toBeVisible();

    await page.reload();
    await expect(page.getByText('RAG MODE ONLINE')).toBeVisible();
  });
});