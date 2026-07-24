import { expect, test } from '@playwright/test';
import { prepareAuthenticatedPage } from './utils/apiMocks';
import { assertQaGuards, installQaGuards } from './utils/qaGuards';

test.describe('capacitor mobile shell', () => {
  test.beforeEach(async ({ page }) => {
    installQaGuards(page);
    await page.setViewportSize({ width: 390, height: 844 });
  });

  test.afterEach(async ({ page }) => {
    await assertQaGuards(page);
  });

  test('shows navigation drawer controls on mobile', async ({ page }) => {
    await prepareAuthenticatedPage(page);
    await expect(page.getByRole('button', { name: 'Open navigation' })).toBeVisible();
    await page.getByRole('button', { name: 'Open navigation' }).click();
    await expect(page.getByTitle('Close navigation')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Start new conversation' })).toBeVisible();
  });

  test('closes navigation drawer after selecting new conversation', async ({ page }) => {
    await prepareAuthenticatedPage(page);
    await page.getByRole('button', { name: 'Open navigation' }).click();
    await expect(page.getByRole('button', { name: 'Dismiss menu overlay' })).toBeVisible();
    await page.getByRole('button', { name: 'Start new conversation' }).click();
    await expect(page.getByRole('button', { name: 'Dismiss menu overlay' })).not.toBeVisible();
    await expect(page.getByTitle('Close navigation')).not.toBeVisible();
  });

  test('toggles theme from settings on mobile', async ({ page }) => {
    await prepareAuthenticatedPage(page);
    await page.getByRole('button', { name: 'Open navigation' }).click();
    await page.getByRole('button', { name: 'Account menu' }).click();
    await page.getByRole('menuitem', { name: 'Settings' }).click();
    await page.getByRole('button', { name: 'Appearance' }).click();
    await page.getByRole('radio', { name: 'Dark' }).click();
    await expect(page.locator('html')).toHaveClass(/dark/);
    await page.getByRole('radio', { name: 'Light' }).click();
    await expect(page.locator('html')).not.toHaveClass(/dark/);
  });
});
