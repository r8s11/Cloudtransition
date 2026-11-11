import { test, expect } from '@playwright/test';
import { spawn } from 'node:child_process';
import { readFileSync, statSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { HELPER, freePort, launch, openPopup, runAutofill, stubContent } from './harness.mjs';

const mode = (p) => statSync(p).mode & 0o777;
const readJson = (h, name) => JSON.parse(readFileSync(path.join(h.helper.home, name), 'utf8'));
const FILLED = { status: 'filled', step: 1, counts: { green: 13, yellow: 1, ai_drafts: 1, ai_calls: 1, fields: 14 } };

async function withHelper(fn, opts) {
  const h = await launch(opts);
  try {
    await fn(h);
  } finally {
    await h.close();
  }
}

// Starts a second helper on the same home and returns what it printed once it listens.
async function secondStart(h) {
  const port = await freePort();
  const proc = spawn('python3', [HELPER, 'serve'], {
    stdio: ['ignore', 'pipe', 'pipe'],
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1', JOB_AUTOFILL_HOME: h.helper.home, JOB_AUTOFILL_PORT: String(port) },
  });
  let out = '';
  try {
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error(`second helper did not start: ${out}`)), 10_000);
      const on = (d) => { out += d; if (out.includes('Helper listening')) { clearTimeout(timer); resolve(); } };
      proc.stdout.on('data', on);
      proc.stderr.on('data', on);
      proc.once('exit', () => { clearTimeout(timer); reject(new Error(`second helper exited: ${out}`)); });
    });
  } finally {
    proc.kill('SIGKILL');
  }
  return out;
}

test('U1: first run — pair the extension with the helper', async () => {
  await withHelper(async (h) => {
    // 1. The helper printed the token once, on its first start.
    expect(h.helper.output()).toContain(`Pairing token: ${h.helper.token}`);
    expect(mode(h.helper.home)).toBe(0o700);
    expect(mode(path.join(h.helper.home, 'token'))).toBe(0o600);
    expect(mode(path.join(h.helper.home, 'config.json'))).toBe(0o600);

    // 2. Unpaired popup.
    await h.page.goto(h.fixtureUrl('index.html'));
    const { popup } = await openPopup(h.page);
    await expect(popup.locator('#status-text')).toHaveText('Not paired');
    await expect(popup.getByText('Not paired with the helper')).toBeVisible();
    await expect(popup.getByLabel('Pairing token')).toBeVisible();
    await expect(popup.getByRole('button', { name: 'Autofill page' })).toBeDisabled();

    // 3. A wrong token is refused and nothing is stored; the right one pairs.
    await popup.getByLabel('Pairing token').fill('not-the-token');
    await popup.getByRole('button', { name: 'Pair', exact: true }).click();
    await expect(popup.locator('#pair-msg')).toContainText('rejected that token');
    expect(await popup.evaluate(async () => (await chrome.storage.local.get('token')).token)).toBeUndefined();

    await popup.getByLabel('Pairing token').fill(h.helper.token);
    await popup.getByRole('button', { name: 'Pair', exact: true }).click();
    await expect(popup.locator('#status-text')).toHaveText(`Helper connected · 127.0.0.1:${h.helper.port}`);
    await expect(popup.getByRole('tab', { name: 'Run' })).toBeVisible();

    // A second helper start on the same home does not print a new token.
    const again = await secondStart(h);
    expect(again).not.toContain('Pairing token');
    expect(readFileSync(path.join(h.helper.home, 'token'), 'utf8').trim()).toBe(h.helper.token);
  });
});

test('U3: edit manual profile fields in the popup', async () => {
  await withHelper(async (h) => {
    await h.pair();
    await h.page.goto(h.fixtureUrl('index.html'));
    let { popup } = await openPopup(h.page);
    await expect(popup.locator('#status-text')).toContainText('Helper connected');
    await popup.getByRole('tab', { name: 'Profile' }).click();

    // Imported fields: read-only, with their source.
    await expect(popup.getByLabel('First name')).toHaveValue('Jordan');
    await expect(popup.getByLabel('First name')).toHaveJSProperty('readOnly', true);
    await expect(popup.getByLabel('Email')).toHaveValue('jordan.avery@example.test');
    await expect(popup.getByLabel('Email')).toHaveJSProperty('readOnly', true);
    await expect(popup.locator('#profile-src')).toContainText('From resume/master.md · read-only');

    await popup.getByLabel('Country').fill('United States');
    await popup.getByLabel('Authorized to work in the US').selectOption('Yes');
    await popup.getByLabel('Needs sponsorship').selectOption('No');
    await popup.getByLabel('Veteran status').selectOption({ label: 'Leave blank' });
    await popup.getByRole('button', { name: 'Save profile' }).click();
    await expect(popup.locator('#profile-msg')).toHaveText('Profile saved');

    const saved = readJson(h, 'profile.json');
    expect(saved).toEqual({
      street: '', zip: '', country: 'United States', workAuthorization: 'Yes', needsSponsorship: 'No',
      gender: '', race: '', veteran: '', disability: '',
    });
    expect(mode(path.join(h.helper.home, 'profile.json'))).toBe(0o600);

    // Reopening the popup shows what was saved.
    await popup.close();
    ({ popup } = await openPopup(h.page));
    await expect(popup.locator('#status-text')).toContainText('Helper connected');
    await popup.getByRole('tab', { name: 'Profile' }).click();
    await expect(popup.getByLabel('Country')).toHaveValue('United States');
    await expect(popup.getByLabel('Authorized to work in the US')).toHaveValue('Yes');
    await expect(popup.getByLabel('Needs sponsorship')).toHaveValue('No');
    await expect(popup.getByLabel('Veteran status')).toHaveValue('');
    await popup.close();
  });
});

test('U3: resume PDF path is set in Profile and its bytes are cached', async () => {
  await withHelper(async (h) => {
    await h.pair();
    await h.page.goto(h.fixtureUrl('index.html'));
    const { popup } = await openPopup(h.page);
    await expect(popup.locator('#status-text')).toContainText('Helper connected');
    await popup.getByRole('tab', { name: 'Profile' }).click();
    await expect(popup.locator('#resume-text')).toContainText('resume.fixture.pdf');
    await expect(popup.locator('#resume-text')).toContainText(' KB');

    // Cached at sync: name, type and base64 of a PDF.
    const resume = await popup.evaluate(async () => (await chrome.storage.local.get('resume')).resume);
    expect(resume.name).toBe('resume.fixture.pdf');
    expect(resume.type).toBe('application/pdf');
    expect(resume.b64.startsWith('JVBERi')).toBe(true);

    // A path that does not exist shows the helper's message and drops the cached bytes.
    await popup.getByRole('button', { name: 'Change' }).click();
    await popup.getByLabel('Path to your resume PDF').fill('/nonexistent/resume.pdf');
    await popup.getByRole('button', { name: 'Use this file' }).click();
    await expect(popup.locator('#resume-error')).toHaveText('AutoFill: Resume file not found — pick it in Profile');
    expect(await popup.evaluate(async () => (await chrome.storage.local.get('resume')).resume)).toBeUndefined();
    expect(readJson(h, 'config.json').resume_pdf).toBe('/nonexistent/resume.pdf');

    // Pointing it back at a real file restores both.
    const pdf = path.resolve('tests/fixtures/resume.fixture.pdf');
    await popup.getByLabel('Path to your resume PDF').fill(pdf);
    await popup.getByRole('button', { name: 'Use this file' }).click();
    await expect(popup.locator('#profile-msg')).toHaveText('Resume file saved');
    await expect(popup.locator('#resume-error')).toBeHidden();
    await expect(popup.locator('#resume-text')).toContainText(pdf);
    expect((await popup.evaluate(async () => (await chrome.storage.local.get('resume')).resume)).name).toBe('resume.fixture.pdf');
    await popup.close();
  });
});

test('U13: pick provider and model from the provider\'s list', async () => {
  await withHelper(async (h) => {
    h.helper.setKey('anthropic', 'test-key-a');
    h.helper.setKey('openai', 'test-key-o');
    await h.pair();
    await h.page.goto(h.fixtureUrl('index.html'));
    const { popup } = await openPopup(h.page);
    await expect(popup.locator('#status-text')).toContainText('Helper connected');
    await popup.getByRole('tab', { name: 'AI' }).click();
    const options = () => popup.locator('#model option').allTextContents();

    // OpenAI: exactly the provider's two ids (plus the placeholder), pick the second, save.
    await popup.getByLabel('OpenAI').check();
    await expect(popup.locator('#model')).toBeEnabled();
    expect(await options()).toEqual(['— pick a model —', 'fake-openai-a', 'fake-openai-b']);
    await expect(popup.locator('#key-line')).toHaveText('Key: saved in Keychain (job-autofill-openai)');
    await popup.locator('#model').selectOption('fake-openai-b');
    await popup.getByRole('button', { name: 'Save', exact: true }).click();
    await expect(popup.locator('#ai-msg')).toHaveText('Saved');
    let cfg = readJson(h, 'config.json');
    expect(cfg.provider).toBe('openai');
    expect(cfg.models.openai).toBe('fake-openai-b');

    // Claude: the list reloads from its own provider and has no saved pick yet.
    await popup.getByLabel('Claude').check();
    await expect(popup.locator('#model option').nth(1)).toHaveText('fake-anthropic-a');
    expect(await options()).toEqual(['— pick a model —', 'fake-anthropic-a', 'fake-anthropic-b']);
    await expect(popup.locator('#model')).toHaveValue('');
    expect(readJson(h, 'config.json').provider).toBe('anthropic');
    await popup.locator('#model').selectOption('fake-anthropic-a');
    await popup.getByRole('button', { name: 'Save', exact: true }).click();
    await expect(popup.locator('#ai-msg')).toHaveText('Saved');

    // Back to OpenAI: its pick is restored; the other provider's pick is kept.
    await popup.getByLabel('OpenAI').check();
    await expect(popup.locator('#model')).toHaveValue('fake-openai-b');
    cfg = readJson(h, 'config.json');
    expect(cfg.models).toEqual({ openai: 'fake-openai-b', anthropic: 'fake-anthropic-a' });

    // Daily cap and debugger fallback are saved with the same button.
    await popup.getByLabel('AI calls per day').fill('12');
    await popup.getByRole('switch', { name: 'Real input for stubborn fields' }).click();
    await popup.getByRole('button', { name: 'Save', exact: true }).click();
    await expect(popup.locator('#ai-msg')).toHaveText('Saved');
    expect(readJson(h, 'config.json').daily_cap).toBe(12);
    expect(await popup.evaluate(async () => (await chrome.storage.local.get('prefs')).prefs)).toEqual({ fallback: false });

    // No key: the exact command is shown and the list is not loaded.
    writeFileSync(path.join(h.helper.home, 'keychain.json'), JSON.stringify({ 'job-autofill-anthropic': 'test-key-a' }));
    await popup.getByLabel('Claude').check();
    await expect(popup.locator('#model option').nth(1)).toHaveText('fake-anthropic-a');
    await popup.getByLabel('OpenAI').check();
    await expect(popup.locator('#ai-error')).toContainText('No OpenAI key — run: python3 job-autofill/helper/server.py set-key openai');
    await expect(popup.locator('#model')).toBeDisabled();
    writeFileSync(path.join(h.helper.home, 'keychain.json'), '{}');
    await popup.getByLabel('Claude').check();
    await expect(popup.locator('#ai-error')).toContainText('No Anthropic key — run: python3 job-autofill/helper/server.py set-key anthropic');
    await popup.close();
  });
});

test('U17: the submit switch is off at the start of every run', async () => {
  await withHelper(async (h) => {
    await h.pair();
    await h.page.goto(h.fixtureUrl('index.html'));
    let stub = await stubContent(h.page, { report: FILLED });

    // A run with the switch on.
    const first = await runAutofill(h.page, { submit: true });
    expect(first.status).toBe('filled');
    expect(first.counts).toMatchObject({ green: 13, yellow: 1, ai_drafts: 1, fields: 14 });
    expect(first.text).toContain('Filled 14 · 1 to review');
    expect(first.run.submit).toBe(true);
    expect((await stub.starts()).map((s) => s.submit)).toEqual([true]);

    // Close and reopen the popup: the switch is off, and nothing about it was stored.
    const { popup, tabId } = await openPopup(h.page);
    const sw = popup.getByRole('switch', { name: 'Continue and submit when safe' });
    await expect(sw).toHaveAttribute('aria-checked', 'false');
    const stored = await popup.evaluate(async () => JSON.stringify([await chrome.storage.local.get(null)]));
    expect(stored).not.toMatch(/submit/i);
    await popup.close();

    // Reload the page and start a new run without touching the switch: fill only.
    await h.page.reload();
    stub = await stubContent(h.page, { report: FILLED });
    const second = await runAutofill(h.page);
    expect(second.tabId).toBe(tabId);
    expect(second.run.submit).toBe(false);
    expect((await stub.starts()).map((s) => s.submit)).toEqual([false]);
  });
});

test('U20: offline popup says so, and a run still uses the last sync', async () => {
  await withHelper(async (h) => {
    await h.pair();
    await h.page.goto(h.fixtureUrl('index.html'));
    const stub = await stubContent(h.page, { report: FILLED });
    await h.helper.stop();

    const { popup } = await openPopup(h.page);
    await expect(popup.locator('#status-text')).toHaveText('Helper offline');
    await expect(popup.locator('#offline-line')).toHaveText(
      /^Helper offline — profile from last sync \(\d{1,2} [A-Z][a-z]{2}, \d{2}:\d{2}\); AI drafts unavailable$/,
    );
    await expect(popup.getByRole('button', { name: 'Autofill page' })).toBeEnabled();

    // AI drafts report why they are unavailable.
    const draft = await popup.evaluate(() => chrome.runtime.sendMessage({ type: 'DRAFT', req: { question: 'Why us?' } }));
    expect(draft).toEqual({ error: 'AutoFill: Helper offline — AI drafts unavailable' });
    await popup.close();

    // The run sends the cached profile and resume reference to the page.
    const run = await runAutofill(h.page);
    expect(run.status).toBe('filled');
    const [start] = await stub.starts();
    expect(start.profile).toMatchObject({ firstName: 'Jordan', lastName: 'Avery', email: 'jordan.avery@example.test' });
    expect(start.resumeRef).toMatchObject({ name: 'resume.fixture.pdf', type: 'application/pdf' });
    expect(start.fallback).toBe(true);
  });
});

test('U20: never-synced offline popup keeps Autofill disabled', async () => {
  await withHelper(async (h) => {
    // Paired with a token but nothing ever synced, and nothing listening on the port.
    await h.worker.evaluate(() => chrome.storage.local.set({ token: 'stale-token', port: 9 }));
    await h.page.goto(h.fixtureUrl('index.html'));
    const { popup } = await openPopup(h.page);
    await expect(popup.locator('#status-text')).toHaveText('Helper offline');
    await expect(popup.getByRole('button', { name: 'Autofill page' })).toBeDisabled();
    await expect(popup.locator('#run-msg')).toHaveText('Autofill needs one sync with the helper first.');
    await popup.close();
  }, { helper: false });
});

test('popup: pages the extension cannot fill', async () => {
  await withHelper(async (h) => {
    await h.pair();
    await h.page.goto('chrome://version');
    const { popup } = await openPopup(h.page);
    await expect(popup.locator('#status-text')).toContainText('Helper connected');
    await expect(popup.getByRole('button', { name: 'Autofill page' })).toBeDisabled();
    await expect(popup.locator('#run-msg')).toHaveText("Can't fill this page");
    await popup.close();
  });
});

test('popup: a page with no form fields says so', async () => {
  await withHelper(async (h) => {
    await h.pair();
    await h.page.goto(h.fixtureUrl('index.html'));
    await stubContent(h.page, { report: { status: 'filled', step: 1, counts: { green: 0, yellow: 0, ai_drafts: 0, ai_calls: 0, fields: 0 } } });
    const run = await runAutofill(h.page);
    expect(run.text).toContain('No form fields found on this page');
  });
});

test('background: DEBUGGER_FILL types trusted text and detaches', async () => {
  await withHelper(async (h) => {
    await h.pair();
    await h.page.goto(h.fixtureUrl('debugger-probe.html'));
    // Simulated input is wiped by the page...
    await h.page.evaluate(() => {
      const el = document.getElementById('probe');
      el.value = 'simulated';
      el.dispatchEvent(new Event('input', { bubbles: true }));
    });
    await expect(h.page.locator('#probe')).toHaveValue('');

    // ...real input through the debugger sticks, and every attach is matched by a detach.
    // (Playwright's own CDP session shows up in chrome.debugger.getTargets, so the calls are counted.)
    const { popup, tabId } = await openPopup(h.page);
    await h.worker.evaluate(() => {
      globalThis.__dbg = { attach: 0, detach: 0 };
      for (const k of ['attach', 'detach']) {
        const orig = chrome.debugger[k].bind(chrome.debugger);
        chrome.debugger[k] = (...a) => { globalThis.__dbg[k]++; return orig(...a); };
      }
    });
    const res = await popup.evaluate((tabId) => chrome.runtime.sendMessage({
      type: 'DEBUGGER_FILL', tabId, frameId: 0, selector: '#probe', kind: 'text', value: 'jordan.avery@example.test',
    }), tabId);
    expect(res).toEqual({ ok: true });
    await expect(h.page.locator('#probe')).toHaveValue('jordan.avery@example.test');
    expect(await h.worker.evaluate(() => globalThis.__dbg)).toEqual({ attach: 1, detach: 1 });
    const missing = await popup.evaluate((tabId) => chrome.runtime.sendMessage({
      type: 'DEBUGGER_FILL', tabId, frameId: 0, selector: '#nope', kind: 'text', value: 'x',
    }), tabId);
    expect(missing).toEqual({ error: 'element not found' });
    await popup.close();
  });
});
