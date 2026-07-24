import { expect, test } from '@playwright/test';

test.describe('public legal pages', () => {
  test('privacy policy is public and links to terms', async ({ page }) => {
    await page.goto('/privacy');

    await expect(page.getByRole('heading', { name: 'Privacy Policy' })).toBeVisible();
    await expect(page.getByText('Information we process')).toBeVisible();
    await expect(page.getByRole('link', { name: 'Terms' })).toHaveAttribute('href', '/terms');
  });

  test('terms are public and link back to CurAI', async ({ page }) => {
    await page.goto('/terms');

    await expect(page.getByRole('heading', { name: 'Terms of Service' })).toBeVisible();
    await expect(page.getByText('Acceptable use')).toBeVisible();
    await expect(page.getByRole('link', { name: 'Back to CurAI' })).toHaveAttribute('href', '/');
  });
});
