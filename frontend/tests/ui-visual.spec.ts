import { expect, test } from '@playwright/test';
import { assertQaGuards, installQaGuards } from './utils/qaGuards';

const stableUiStyles = `
  *, *::before, *::after {
    animation: none !important;
    transition: none !important;
    caret-color: transparent !important;
  }

  .terminal-cursor {
    animation: none !important;
    opacity: 1 !important;
  }
`;

async function preparePage(page: import('@playwright/test').Page) {
  await page.addStyleTag({ content: stableUiStyles });
  await page.goto('/');
  await page.evaluate(() => {
    localStorage.clear();
  });
  await page.goto('/');
  await page.addStyleTag({ content: stableUiStyles });
}

async function setUiMode(page: import('@playwright/test').Page, mode: 'classic' | 'terminal') {
  await page.evaluate((targetMode) => {
    localStorage.setItem('personal-ai-ui-mode', JSON.stringify(targetMode));
    if (targetMode === 'terminal') {
      localStorage.setItem('personal-ai-mode', JSON.stringify('chat'));
    }
  }, mode);
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

  test('classic desktop empty state', async ({ page }) => {
    await preparePage(page);
    await expect(page.getByText('Start a smart-routed conversation')).toBeVisible();
    await expect(page.locator('#root')).toHaveScreenshot('classic-desktop.png');
  });

  test('terminal desktop empty state', async ({ page }) => {
    await preparePage(page);
    await setUiMode(page, 'terminal');
    await expect(page.getByText('CHAT MODE ONLY')).toBeVisible();
    await expect(page.locator('#root')).toHaveScreenshot('terminal-desktop.png');
  });

  test('classic mobile empty state', async ({ page, isMobile }) => {
    await preparePage(page);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/');
    await page.addStyleTag({ content: stableUiStyles });
    if (!isMobile) {
      await setUiMode(page, 'classic');
    }
    await expect(page.getByText('Start a smart-routed conversation')).toBeVisible();
    await expect(page.locator('#root')).toHaveScreenshot('classic-mobile.png');
  });

  test('terminal mobile empty state', async ({ page }) => {
    await preparePage(page);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/');
    await page.addStyleTag({ content: stableUiStyles });
    await setUiMode(page, 'terminal');
    await expect(page.getByText('CHAT MODE ONLY')).toBeVisible();
    await expect(page.locator('#root')).toHaveScreenshot('terminal-mobile.png');
  });
});