import { defineConfig } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.dirname(fileURLToPath(import.meta.url));

// Browsers and temp files live on the USB volume; the internal disk is full.
process.env.PLAYWRIGHT_BROWSERS_PATH ||= path.join(root, '.cache', 'ms-playwright');
process.env.TMPDIR ||= '/Volumes/SANDISK USB/work/tmp';

export default defineConfig({
  testDir: path.join(root, 'tests', 'e2e'),
  testMatch: '**/*.spec.mjs',
  timeout: 60_000,
  workers: 1,
  fullyParallel: false,
  reporter: [['list']],
  outputDir: path.join(root, 'test-results'),
});
