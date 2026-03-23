import { expect, test } from '@playwright/test';

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

test.describe('cross-browser UI visual baselines', () => {
  test('classic desktop empty state', async ({ page }) => {
    await preparePage(page);
    await expect(page.getByText('Start a grounded conversation')).toBeVisible();
    await expect(page.locator('#root')).toHaveScreenshot('classic-desktop.png');
  });

  test('terminal desktop empty state', async ({ page }) => {
    await preparePage(page);
    await page.getByRole('button', { name: 'TERMINAL' }).click();
    await expect(page.getByText('RAG MODE ONLINE')).toBeVisible();
    await expect(page.locator('#root')).toHaveScreenshot('terminal-desktop.png');
  });

  test('classic mobile empty state', async ({ page, isMobile }) => {
    await preparePage(page);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/');
    await page.addStyleTag({ content: stableUiStyles });
    if (!isMobile) {
      await page.evaluate(() => {
        localStorage.setItem('personal-ai-ui-mode', 'classic');
      });
      await page.goto('/');
      await page.addStyleTag({ content: stableUiStyles });
    }
    await expect(page.getByText('Start a grounded conversation')).toBeVisible();
    await expect(page.locator('#root')).toHaveScreenshot('classic-mobile.png');
  });

  test('terminal mobile empty state', async ({ page }) => {
    await preparePage(page);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/');
    await page.addStyleTag({ content: stableUiStyles });
    await page.getByRole('button', { name: 'TERMINAL' }).click();
    await expect(page.getByText('RAG MODE ONLINE')).toBeVisible();
    await expect(page.locator('#root')).toHaveScreenshot('terminal-mobile.png');
  });
});