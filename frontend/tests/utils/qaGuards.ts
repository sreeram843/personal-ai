import { expect, type Page } from '@playwright/test';

type GuardOptions = {
  ignoreConsolePatterns?: RegExp[];
  ignoreNetworkPatterns?: RegExp[];
};

type GuardState = {
  consoleErrors: string[];
  networkErrors: string[];
};

const defaultIgnoredNetwork = [/\/favicon\.ico$/i, /\/playwright-report\//i, /fonts\.gstatic\.com/i];
const guardState = new WeakMap<Page, GuardState>();

function isIgnored(text: string, patterns: RegExp[]): boolean {
  return patterns.some((pattern) => pattern.test(text));
}

export function installQaGuards(page: Page, options: GuardOptions = {}): void {
  const state: GuardState = {
    consoleErrors: [],
    networkErrors: [],
  };

  const ignoredConsole = options.ignoreConsolePatterns ?? [];
  const ignoredNetwork = [...defaultIgnoredNetwork, ...(options.ignoreNetworkPatterns ?? [])];

  page.on('console', (msg) => {
    if (msg.type() !== 'error') {
      return;
    }

    const text = msg.text();
    if (!isIgnored(text, ignoredConsole)) {
      state.consoleErrors.push(text);
    }
  });

  page.on('requestfailed', (request) => {
    const details = `${request.method()} ${request.url()} :: ${request.failure()?.errorText ?? 'request failed'}`;
    if (!isIgnored(details, ignoredNetwork)) {
      state.networkErrors.push(details);
    }
  });

  page.on('response', (response) => {
    if (response.status() < 500) {
      return;
    }

    const details = `${response.status()} ${response.request().method()} ${response.url()}`;
    if (!isIgnored(details, ignoredNetwork)) {
      state.networkErrors.push(details);
    }
  });

  guardState.set(page, state);
}

export async function assertQaGuards(page: Page): Promise<void> {
  const state = guardState.get(page);
  expect(state, 'QA guard state was not installed for this page').toBeDefined();

  expect.soft(state?.consoleErrors ?? [], 'Unexpected browser console errors').toEqual([]);
  expect.soft(state?.networkErrors ?? [], 'Unexpected network failures or 5xx responses').toEqual([]);

  const mainCount = await page.locator('main,[role="main"]').count();
  expect.soft(mainCount, 'Expected a main landmark for screen reader navigation').toBeGreaterThan(0);

  const inputCount = await page.locator('textarea,input[type="text"],input:not([type]),[role="textbox"]').count();
  expect.soft(inputCount, 'Expected at least one text input control').toBeGreaterThan(0);

  const unnamedButtons = await page.evaluate(() => {
    const buttons = Array.from(document.querySelectorAll('button'));
    return buttons
      .filter((button) => !button.disabled)
      .filter((button) => {
        const text = (button.textContent ?? '').trim();
        const ariaLabel = (button.getAttribute('aria-label') ?? '').trim();
        const title = (button.getAttribute('title') ?? '').trim();
        const labelledBy = (button.getAttribute('aria-labelledby') ?? '').trim();
        return text.length === 0 && ariaLabel.length === 0 && title.length === 0 && labelledBy.length === 0;
      })
      .map((button) => button.outerHTML.slice(0, 140));
  });

  expect.soft(unnamedButtons, 'Buttons should expose visible text or accessible labels').toEqual([]);
}
