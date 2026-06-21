import { expect, test } from '@playwright/test';
import { installApiBootstrapMocks } from './utils/apiMocks';
import { assertQaGuards, installQaGuards } from './utils/qaGuards';

const stableUiStyles = `
  *, *::before, *::after {
    animation: none !important;
    transition: none !important;
    caret-color: transparent !important;
  }
`;

async function preparePage(page: import('@playwright/test').Page) {
  await installApiBootstrapMocks(page);
  await page.addStyleTag({ content: stableUiStyles });
  await page.goto('/');
  await page.evaluate(() => {
    localStorage.clear();
  });
  await page.goto('/');
  await page.addStyleTag({ content: stableUiStyles });
}

test.describe('cross-browser UI visual baselines', () => {
  test.beforeEach(async ({ page }) => {
    installQaGuards(page);
  });

  test.afterEach(async ({ page }) => {
    await assertQaGuards(page);
  });

  test('desktop empty state', async ({ page }) => {
    await preparePage(page);
    await expect(page.getByText('Start a smart-routed conversation')).toBeVisible();
    await expect(page.locator('#root')).toHaveScreenshot('classic-desktop.png');
  });

  test('mobile empty state', async ({ page }) => {
    await preparePage(page);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/');
    await page.addStyleTag({ content: stableUiStyles });
    await expect(page.getByText('Start a smart-routed conversation')).toBeVisible();
    await expect(page.locator('#root')).toHaveScreenshot('classic-mobile.png');
  });
});