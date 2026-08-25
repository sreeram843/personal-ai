import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { prepareAuthenticatedPage } from './utils/apiMocks';
import { assertQaGuards, installQaGuards } from './utils/qaGuards';

async function expectNoCriticalAxeViolations(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page }).exclude('iframe').analyze();
  // Serious/moderate issues (often color-contrast on dim labels) are allowed for now.
  const critical = results.violations
    .filter((violation) => violation.impact === 'critical')
    .map((violation) => ({
      id: violation.id,
      help: violation.help,
      nodes: violation.nodes.map((node) => node.target),
    }));
  expect(critical, 'Expected no critical axe violations').toEqual([]);
}

async function tabUntilFocused(page: Page, name: string, maxTabs = 40): Promise<void> {
  const target = page.getByRole('button', { name });
  for (let i = 0; i < maxTabs; i += 1) {
    if (await target.evaluate((element) => element === document.activeElement)) {
      return;
    }
    await page.keyboard.press('Tab');
  }
  await expect(target, `Tab did not reach "${name}"`).toBeFocused();
}

test.describe('accessibility', () => {
  test.beforeEach(async ({ page }) => {
    installQaGuards(page, {
      ignoreConsolePatterns: [/accounts\.google/i, /gsi\/client/i, /googleapis\.com/i],
      ignoreNetworkPatterns: [/accounts\.google/i, /gsi\/client/i, /googleapis\.com/i],
    });
  });

  test('public legal pages have no critical axe violations', async ({ page }) => {
    await page.goto('/privacy');
    await expect(page.getByRole('heading', { name: 'Privacy Policy' })).toBeVisible();
    await expectNoCriticalAxeViolations(page);

    await page.goto('/terms');
    await expect(page.getByRole('heading', { name: 'Terms of Service' })).toBeVisible();
    await expectNoCriticalAxeViolations(page);
  });

  test('login page has no critical axe violations', async ({ page }) => {
    await page.route('**/auth/config', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          auth_disabled: false,
          google_client_id: 'playwright-tests.apps.googleusercontent.com',
          google_auth_enabled: true,
          support_email: 'hello@cura-i.com',
        }),
      });
    });
    await page.addInitScript(() => {
      localStorage.clear();
    });
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { name: 'CurieAI' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Privacy' })).toBeVisible();
    await expectNoCriticalAxeViolations(page);
  });

  test('chat page has no critical axe violations and supports keyboard flows', async ({ page }) => {
    await prepareAuthenticatedPage(page, {
      conversations: [{ id: 'conv-a11y', title: 'Keyboard trap chat', message_count: 2 }],
    });
    await expectNoCriticalAxeViolations(page);

    const canTab = test.info().project.name !== 'webkit';
    const messageInput = page.getByRole('textbox', { name: 'Message input' });
    await messageInput.fill('Hello from keyboard');
    await messageInput.click();
    await expect(messageInput).toBeFocused();
    // Playwright WebKit does not move focus with Tab (textarea blurs to body).
    if (canTab) {
      await tabUntilFocused(page, 'Send message');
      await expect(page.getByRole('button', { name: 'Send message' })).toBeFocused();
    }

    await page.getByRole('button', { name: 'Actions for Keyboard trap chat' }).click();
    await page.getByRole('menuitem', { name: 'Delete' }).click();
    const confirm = page.getByRole('alertdialog', { name: 'Delete conversation' });
    await expect(confirm).toBeVisible();
    await expect(page.getByRole('button', { name: 'Delete' })).toBeFocused();
    if (canTab) {
      await page.keyboard.press('Tab');
      await expect(page.getByRole('button', { name: 'Cancel' })).toBeFocused();
      await page.keyboard.press('Tab');
      await expect(page.getByRole('button', { name: 'Delete' })).toBeFocused();
    }
    await page.keyboard.press('Escape');
    await expect(confirm).not.toBeVisible();

    await page.getByRole('button', { name: 'Account menu' }).click();
    await page.getByRole('menuitem', { name: 'About' }).click();
    const about = page.getByRole('dialog', { name: 'About CurieAI' });
    await expect(about).toBeVisible();
    await expect(about.getByRole('link', { name: 'hello@cura-i.com' })).toHaveAttribute(
      'href',
      'mailto:hello@cura-i.com',
    );
    await expect(page.getByRole('button', { name: 'Close about panel' })).toBeFocused();
    if (canTab) {
      await page.keyboard.press('Tab');
      await expect(about.getByRole('link', { name: 'hello@cura-i.com' })).toBeFocused();
      await page.keyboard.press('Tab');
      await expect(page.getByRole('button', { name: 'Close about panel' })).toBeFocused();
    }
    await page.keyboard.press('Escape');
    await expect(about).not.toBeVisible();

    await assertQaGuards(page);
  });
});
