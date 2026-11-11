import { test, expect } from '@playwright/test';
import { launch } from './harness.mjs';

test('harness: extension loads', async () => {
  const h = await launch({ helper: false });
  try {
    expect(h.extId).toMatch(/^[a-p]{32}$/);
    const name = await h.worker.evaluate(() => chrome.runtime.getManifest().name);
    expect(name).toBe('AutoFill — job applications');
    await h.page.goto(h.fixtureUrl('index.html'));
    await expect(h.page.locator('h1')).toHaveText('Fixture index');
    // The second fixture origin is a different port and also serves the page.
    expect(h.fixtureUrl('index.html', 'A')).not.toBe(h.fixtureUrl('index.html', 'B'));
    await h.page.goto(h.fixtureUrl('index.html', 'B'));
    await expect(h.page.locator('h1')).toHaveText('Fixture index');
  } finally {
    await h.close();
  }
});
