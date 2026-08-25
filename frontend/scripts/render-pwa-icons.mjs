import { mkdirSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const svgPath = resolve(root, 'public/curai-favicon.svg');
const outDir = resolve(root, 'public/icons');
mkdirSync(outDir, { recursive: true });

let svg = readFileSync(svgPath, 'utf8').replace(/<\?xml[^>]*\?>\s*/u, '');
svg = svg.replace(/@media \(prefers-color-scheme: dark\) \{[\s\S]*?\n\s*\}/u, '');

const targets = [
  { size: 192, name: 'icon-192.png' },
  { size: 512, name: 'icon-512.png' },
  { size: 180, name: 'apple-touch-icon.png' },
];

const browser = await chromium.launch();
try {
  for (const { size, name } of targets) {
    const page = await browser.newPage({
      viewport: { width: size, height: size },
      deviceScaleFactor: 1,
    });
    await page.emulateMedia({ colorScheme: 'light' });
    await page.setContent(
      `<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <style>
      html, body { margin: 0; width: ${String(size)}px; height: ${String(size)}px; background: transparent; overflow: hidden; }
      svg { display: block; width: ${String(size)}px; height: ${String(size)}px; }
    </style>
  </head>
  <body>${svg}</body>
</html>`,
      { waitUntil: 'load' },
    );
    await page.screenshot({
      path: resolve(outDir, name),
      omitBackground: true,
      type: 'png',
    });
    await page.close();
  }
} finally {
  await browser.close();
}
