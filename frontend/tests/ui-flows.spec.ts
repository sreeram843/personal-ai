import { expect, test, type Page } from '@playwright/test';
import { mockConversationMessages, mockIngestFiles, mockSseStream, prepareAuthenticatedPage } from './utils/apiMocks';
import { assertQaGuards, installQaGuards } from './utils/qaGuards';

async function preparePage(page: Page, mode?: 'chat' | 'smart') {
  await prepareAuthenticatedPage(page, { mode });
}

async function fillComposer(page: Page, text: string) {
  const input = page.getByRole('textbox', { name: 'Message input' });
  await input.click();
  await input.fill(text);
  await expect(input).toHaveValue(text);
  await expect(page.getByRole('button', { name: 'Send message' })).toBeEnabled();
}

test.describe('browser interaction flows', () => {
  test.beforeEach(async ({ page }) => {
    installQaGuards(page);
  });

  test.afterEach(async ({ page }) => {
    await assertQaGuards(page);
  });

  test('classic quick chat sends a prompt and new chat clears history', async ({ page }) => {
    await mockConversationMessages(page, 'conv-1', [
      { id: 'u1', role: 'user', content: 'Explain the cache path' },
      { id: 'a1', role: 'assistant', content: 'CACHE PIPELINE VERIFIED' },
    ]);

    await mockSseStream(
      page,
      '/chat/stream',
      [
        `data: ${JSON.stringify({ type: 'conversation', conversation_id: 'conv-1' })}`,
        `data: ${JSON.stringify({
          type: 'final',
          response: {
            message: 'CACHE PIPELINE VERIFIED',
            conversation_id: 'conv-1',
          },
        })}`,
      ].join('\n\n') + '\n\n',
    );

    await preparePage(page, 'chat');
    await fillComposer(page, 'Explain the cache path');
    await page.getByRole('button', { name: 'Send message' }).click();

    await expect(page.getByRole('log').getByText('Explain the cache path', { exact: true })).toBeVisible();
    await expect(page.getByText('CACHE PIPELINE VERIFIED')).toBeVisible();

    await page.getByRole('button', { name: 'Start new conversation' }).click();
    await expect(page.getByText('Start a direct model conversation')).toBeVisible();
    await expect(page.getByText('CACHE PIPELINE VERIFIED')).not.toBeVisible();
  });

  test('smart flow returns assistant response with sources panel', async ({ page }) => {
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

    await mockSseStream(
      page,
      '/smart_chat/stream',
      `data: ${JSON.stringify({
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
    );

    await preparePage(page);
    await fillComposer(page, 'Summarize the ops guidance');
    await page.getByRole('button', { name: 'Send message' }).click();

    await expect(page.getByText('SMART RESPONSE READY')).toBeVisible();
    await expect(page.getByText('Sources', { exact: true })).toBeVisible();
    await page.getByText('Sources', { exact: true }).click();
    await expect(page.getByText('ops-runbook.md', { exact: true })).toBeVisible();
    await expect(page.getByText('Workflow trace', { exact: true })).not.toBeVisible();
  });

  test('document upload shows a success status', async ({ page }) => {
    await mockIngestFiles(page, { count: 1 });

    await preparePage(page);
    // Set files directly on the hidden input — avoids Firefox headless crashes from native picker on Linux CI.
    await page.locator('input[type="file"]').setInputFiles({
      name: 'sample-notes.md',
      mimeType: 'text/markdown',
      buffer: Buffer.from('# Sample\n\nThis file is used for Playwright upload coverage.\n', 'utf-8'),
    });

    await expect(page.getByText('sample-notes.md', { exact: true })).toBeVisible();
    await expect(page.getByText('SUCCESS', { exact: true })).toBeVisible();
    await expect(page.getByText(/Uploaded sample-notes\.md/)).toBeVisible();
  });

  test('upload then smart chat can return a cited assistant response', async ({ page }) => {
    await mockConversationMessages(page, 'conv-upload-1', [
      {
        id: 'u1',
        role: 'user',
        content: 'Summarize my uploaded notes',
      },
      {
        id: 'a1',
        role: 'assistant',
        content: 'According to [sample-notes.md], the upload pipeline is verified.',
      },
    ]);

    await mockIngestFiles(page, { count: 2 });

    await mockSseStream(
      page,
      '/smart_chat/stream',
      [
        `data: ${JSON.stringify({ type: 'conversation', conversation_id: 'conv-upload-1' })}`,
        `data: ${JSON.stringify({
          type: 'final',
          response: {
            message: 'According to [sample-notes.md], the upload pipeline is verified.',
            conversation_id: 'conv-upload-1',
            sources: [
              {
                id: 'doc-upload-1',
                score: 0.991,
                metadata: {
                  name: 'sample-notes.md',
                  path: 'sample-notes.md',
                },
              },
            ],
          },
        })}`,
      ].join('\n\n') + '\n\n',
    );

    await preparePage(page);
    await page.locator('input[type="file"]').setInputFiles({
      name: 'sample-notes.md',
      mimeType: 'text/markdown',
      buffer: Buffer.from('# Sample\n\nUpload pipeline verified.\n', 'utf-8'),
    });
    await expect(page.getByText('SUCCESS', { exact: true })).toBeVisible();

    await fillComposer(page, 'Summarize my uploaded notes');
    await page.getByRole('button', { name: 'Send message' }).click();

    await expect(page.getByRole('log')).toContainText('upload pipeline is verified');
  });
});