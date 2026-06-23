#!/usr/bin/env node
/**
 * Sync CricClubs player profile into app/prompts/demo-cricket.md for the portfolio demo.
 *
 * CricClubs is behind Cloudflare — if headless fetch fails, use --headed and complete
 * the browser check once.
 *
 * Usage:
 *   node scripts/sync_demo_cricket_profile.mjs
 *   node scripts/sync_demo_cricket_profile.mjs --headed
 *   node scripts/sync_demo_cricket_profile.mjs "https://cricclubs.com/LPCL/viewPlayer.do?playerId=1259840&clubId=1089463"
 */

import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const OUT_PATH = resolve(ROOT, 'app/prompts/demo-cricket.md');
const PLAYWRIGHT_PATH = resolve(ROOT, 'frontend/node_modules/playwright/index.mjs');
const DEFAULT_URL =
  'https://cricclubs.com/LPCL/viewPlayer.do?playerId=1259840&clubId=1089463';

const args = process.argv.slice(2).filter((arg) => !arg.startsWith('--'));
const headed = process.argv.includes('--headed');
const fromFileIdx = process.argv.indexOf('--from-file');
const fromFile = fromFileIdx >= 0 ? process.argv[fromFileIdx + 1] : null;
const profileUrl = args[0] || DEFAULT_URL;

function cleanLine(line) {
  return line.replace(/\s+/g, ' ').trim();
}

function extractProfileLines(bodyText) {
  const lines = bodyText
    .split('\n')
    .map(cleanLine)
    .filter((line) => line.length > 0);

  const blocked = /cloudflare|performing security verification|enable javascript/i;
  if (lines.some((line) => blocked.test(line)) && lines.length < 40) {
    throw new Error(
      'Cloudflare blocked the fetch. Re-run with --headed and complete the browser check.',
    );
  }

  const startIdx = lines.findIndex((line) => /sriram mentey/i.test(line));
  const slice = startIdx >= 0 ? lines.slice(startIdx) : lines;
  return slice.slice(0, 220);
}

function buildMarkdown(profileUrl, lines) {
  const summary = lines.join('\n');
  return `# Cricket profile (Sriram Mentey)

Source: [CricClubs LPCL player profile](${profileUrl})  
CricClubs player ID: **1259840** | Club ID: **1089463** (Lonestar Premier Cricket League)

Answer cricket questions using the facts below. If a stat is not listed, say it is not in this synced profile.

## Profile snapshot (auto-synced)

\`\`\`text
${summary}
\`\`\`

## Quick reference

- **Profile link:** ${profileUrl}
- **League:** Lonestar Premier Cricket League (LPCL), Austin / Central Texas area
- Re-sync after new seasons: \`node scripts/sync_demo_cricket_profile.mjs --headed\`
`;
}

async function main() {
  let bodyText = '';
  if (fromFile) {
    const raw = readFileSync(fromFile, 'utf8');
    bodyText = raw
      .replace(/<script[\s\S]*?<\/script>/gi, ' ')
      .replace(/<style[\s\S]*?<\/style>/gi, ' ')
      .replace(/<[^>]+>/g, '\n')
      .replace(/&nbsp;/g, ' ')
      .replace(/&amp;/g, '&');
  } else {
    const { chromium } = await import(pathToFileURL(PLAYWRIGHT_PATH).href);
    const launchOptions = headed
      ? { headless: false, channel: 'chrome' }
      : { headless: true };
    const browser = await chromium.launch(launchOptions);
    const page = await browser.newPage();
    try {
      await page.goto(profileUrl, { waitUntil: 'domcontentloaded', timeout: 120_000 });
      await page
        .waitForFunction(
          () =>
            document.body?.innerText?.includes('Sriram Mentey') ||
            document.body?.innerText?.includes('Playing Role'),
          { timeout: headed ? 90_000 : 20_000 },
        )
        .catch(() => undefined);
      await page.waitForTimeout(2_000);
      bodyText = await page.locator('body').innerText();
    } finally {
      await browser.close();
    }
  }

  const lines = extractProfileLines(bodyText);
  const markdown = buildMarkdown(profileUrl, lines);
  writeFileSync(OUT_PATH, markdown, 'utf8');
  console.log(`Wrote ${OUT_PATH} (${lines.length} lines)`);
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
});
