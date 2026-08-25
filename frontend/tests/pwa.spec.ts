import { expect, test } from '@playwright/test';

test.describe('PWA', () => {
  test('manifest is public and named CurieAI', async ({ request }) => {
    const response = await request.get('/manifest.webmanifest');
    expect(response.status()).toBe(200);
    const manifest = (await response.json()) as { name: string };
    expect(manifest.name).toBe('CurieAI');
  });
});
