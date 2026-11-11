// Playwright harness: loads the unpacked extension in Chromium, serves fixtures on two
// origins, and (when they exist) starts the helper and the fake AI provider.
import { chromium } from '@playwright/test';
import http from 'node:http';
import net from 'node:net';
import { spawn } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, rmSync, mkdirSync } from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const EXTENSION = path.join(ROOT, 'extension');
const FIXTURES = path.join(ROOT, 'tests', 'fixtures', 'ats');
const HELPER = path.join(ROOT, 'helper', 'server.py');
const PROVIDER = path.join(ROOT, 'tests', 'fake_provider.py');

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json',
  '.pdf': 'application/pdf',
  '.png': 'image/png',
};

function tmpBase() {
  const base = process.env.TMPDIR || os.tmpdir();
  mkdirSync(base, { recursive: true });
  return base;
}

function freePort() {
  return new Promise((resolve, reject) => {
    const s = net.createServer();
    s.once('error', reject);
    s.listen(0, '127.0.0.1', () => {
      const { port } = s.address();
      s.close(() => resolve(port));
    });
  });
}

function startStatic(dir) {
  const server = http.createServer((req, res) => {
    const rel = decodeURIComponent(new URL(req.url, 'http://x').pathname).replace(/^\/+/, '') || 'index.html';
    const file = path.resolve(dir, rel);
    if (!file.startsWith(dir + path.sep) || !existsSync(file)) {
      res.writeHead(404).end('not found');
      return;
    }
    res.writeHead(200, { 'content-type': MIME[path.extname(file)] || 'application/octet-stream' });
    res.end(readFileSync(file));
  });
  return new Promise((resolve) => {
    server.listen(0, '127.0.0.1', () => resolve({ server, port: server.address().port }));
  });
}

async function waitForPort(port, ms = 10_000) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    const ok = await new Promise((resolve) => {
      const s = net.connect(port, '127.0.0.1');
      s.once('connect', () => { s.destroy(); resolve(true); });
      s.once('error', () => resolve(false));
    });
    if (ok) return;
    await new Promise((r) => setTimeout(r, 100));
  }
  throw new Error(`nothing listening on 127.0.0.1:${port} after ${ms} ms`);
}

async function startProvider() {
  if (!existsSync(PROVIDER)) throw new Error(`launch({helper:true}) needs ${PROVIDER}, which does not exist yet`);
  const port = await freePort();
  const proc = spawn('python3', [PROVIDER, String(port)], { stdio: 'ignore', env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' } });
  await waitForPort(port);
  const base = `http://127.0.0.1:${port}`;
  return {
    port,
    proc,
    // Fake provider contract (Task 4): GET /__requests -> JSON array; POST /__mode {mode}.
    requests: async () => (await globalThis.fetch(`${base}/__requests`)).json(),
    setMode: async (mode) => {
      await globalThis.fetch(`${base}/__mode`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ mode }),
      });
    },
  };
}

async function startHelper(home, provider) {
  if (!existsSync(HELPER)) throw new Error(`launch({helper:true}) needs ${HELPER}, which does not exist yet`);
  const port = await freePort();
  const providerUrl = `http://127.0.0.1:${provider.port}`;
  const proc = spawn('python3', [HELPER, 'serve'], {
    stdio: 'ignore',
    env: {
      ...process.env,
      PYTHONDONTWRITEBYTECODE: '1',
      JOB_AUTOFILL_HOME: home,
      JOB_AUTOFILL_PORT: String(port),
      JOB_AUTOFILL_KEYCHAIN: `fake:${path.join(home, 'keychain.json')}`,
      JOB_AUTOFILL_ANTHROPIC_URL: providerUrl,
      JOB_AUTOFILL_OPENAI_URL: providerUrl,
    },
  });
  await waitForPort(port);
  const tokenFile = path.join(home, 'token');
  const token = existsSync(tokenFile) ? readFileSync(tokenFile, 'utf8').trim() : null;
  return { port, token, home, proc };
}

function killProc(proc) {
  return new Promise((resolve) => {
    if (!proc || proc.exitCode !== null) return resolve();
    proc.once('exit', () => resolve());
    proc.kill('SIGTERM');
    setTimeout(() => proc.kill('SIGKILL'), 2000).unref();
  });
}

export async function launch({ fallback = true, helper = true } = {}) {
  const work = mkdtempSync(path.join(tmpBase(), 'jaf-e2e-'));
  const home = path.join(work, 'home');
  mkdirSync(home, { recursive: true, mode: 0o700 });

  const [a, b] = await Promise.all([startStatic(FIXTURES), startStatic(FIXTURES)]);
  const ports = { A: a.port, B: b.port };

  let provider = null;
  let helperInfo = null;
  if (helper) {
    provider = await startProvider();
    helperInfo = await startHelper(home, provider);
  }

  const context = await chromium.launchPersistentContext(path.join(work, 'profile'), {
    channel: 'chromium',
    headless: true,
    args: [`--disable-extensions-except=${EXTENSION}`, `--load-extension=${EXTENSION}`],
  });
  let [worker] = context.serviceWorkers();
  worker ||= await context.waitForEvent('serviceworker', { timeout: 15_000 });
  const extId = new URL(worker.url()).host;
  if (fallback === false) {
    await worker.evaluate(() => chrome.storage.local.set({ prefs: { fallback: false } }));
  }
  const page = context.pages()[0] ?? (await context.newPage());

  return {
    context,
    extId,
    page,
    worker,
    helper: helperInfo && {
      port: helperInfo.port,
      token: helperInfo.token,
      home,
      stop: () => killProc(helperInfo.proc),
    },
    provider: provider && { port: provider.port, requests: provider.requests, setMode: provider.setMode },
    fixtureUrl: (name, port = 'A') => `http://127.0.0.1:${ports[port]}/${name}`,
    async close() {
      await context.close();
      await killProc(helperInfo?.proc);
      await killProc(provider?.proc);
      await Promise.all([a, b].map((s) => new Promise((r) => s.server.close(r))));
      rmSync(work, { recursive: true, force: true });
    },
  };
}

// Opens the popup for `page`'s tab, optionally turns on "Continue and submit when safe",
// clicks "Autofill page" and waits for the run to settle. Returns the popup's visible text
// as `{ text }`. The popup UI lands in the background/popup task; until then this helper
// cannot find its controls and throws with a clear message.
export async function runAutofill(page, { submit = false } = {}) {
  const context = page.context();
  const [worker] = context.serviceWorkers();
  const extId = new URL(worker.url()).host;
  const tabId = await worker.evaluate(async (url) => {
    const tabs = await chrome.tabs.query({ url });
    return tabs[0]?.id ?? null;
  }, page.url());
  if (tabId == null) throw new Error(`runAutofill: no tab found for ${page.url()}`);

  const popup = await context.newPage();
  await popup.goto(`chrome-extension://${extId}/popup/popup.html?tab=${tabId}`);
  const run = popup.getByRole('button', { name: 'Autofill page' });
  if (!(await run.count())) throw new Error('runAutofill: popup has no "Autofill page" button yet');
  if (submit) await popup.getByRole('switch', { name: /Continue and submit when safe/ }).click();
  await run.click();
  await popup.getByRole('button', { name: 'Autofill page' }).waitFor({ state: 'visible', timeout: 30_000 });
  const text = await popup.locator('body').innerText();
  await popup.close();
  return { text };
}
