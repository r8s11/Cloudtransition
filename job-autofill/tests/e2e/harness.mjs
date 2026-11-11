// Playwright harness: loads the unpacked extension in Chromium, serves fixtures on two
// origins, and (when they exist) starts the helper and the fake AI provider.
import { chromium } from '@playwright/test';
import http from 'node:http';
import net from 'node:net';
import { spawn } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, rmSync, mkdirSync, statSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const EXTENSION = path.join(ROOT, 'extension');
const FIXTURES = path.join(ROOT, 'tests', 'fixtures', 'ats');
export const HELPER = path.join(ROOT, 'helper', 'server.py');
const PROVIDER = path.join(ROOT, 'tests', 'fake_provider.py');
const FIXTURE_MD = path.join(ROOT, 'tests', 'fixtures', 'master.fixture.md');
const FIXTURE_PDF = path.join(ROOT, 'tests', 'fixtures', 'resume.fixture.pdf');

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

export function freePort() {
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
    const rel = decodeURIComponent(new URL(req.url, 'http://x').pathname).replace(/^\/+/, '');
    let file = path.resolve(dir, rel);
    if (file !== dir && !file.startsWith(dir + path.sep)) {
      res.writeHead(404).end('not found');
      return;
    }
    // A directory (including the root) serves its index.html; anything that is not a file is a 404.
    if (existsSync(file) && statSync(file).isDirectory()) file = path.join(file, 'index.html');
    if (!existsSync(file) || !statSync(file).isFile()) {
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
  // The helper keeps whatever config.json exists, so the fixture resume PDF is set up front.
  writeFileSync(path.join(home, 'config.json'), JSON.stringify({ resume_pdf: FIXTURE_PDF }) + '\n', { mode: 0o600 });
  const proc = spawn('python3', [HELPER, 'serve'], {
    stdio: ['ignore', 'pipe', 'pipe'],
    env: {
      ...process.env,
      PYTHONDONTWRITEBYTECODE: '1',
      JOB_AUTOFILL_HOME: home,
      JOB_AUTOFILL_PORT: String(port),
      JOB_AUTOFILL_KEYCHAIN: `fake:${path.join(home, 'keychain.json')}`,
      JOB_AUTOFILL_RESUME_MD: FIXTURE_MD,
      JOB_AUTOFILL_ANTHROPIC_URL: providerUrl,
      JOB_AUTOFILL_OPENAI_URL: providerUrl,
    },
  });
  let output = '';
  proc.stdout.on('data', (d) => { output += d; });
  proc.stderr.on('data', (d) => { output += d; });
  await waitForPort(port);
  const tokenFile = path.join(home, 'token');
  const token = existsSync(tokenFile) ? readFileSync(tokenFile, 'utf8').trim() : null;
  return { port, token, home, proc, output: () => output };
}

function killProc(proc) {
  return new Promise((resolve) => {
    if (!proc || proc.exitCode !== null || proc.signalCode !== null) return resolve();
    proc.once('exit', () => resolve());
    proc.kill('SIGTERM');
    setTimeout(() => proc.kill('SIGKILL'), 2000).unref();
  });
}

const EXT_IDS = new WeakMap(); // browser context -> extension id

// The extension's service worker. A sleeping worker is woken by opening an extension page.
async function serviceWorker(context) {
  let [worker] = context.serviceWorkers();
  if (worker) return worker;
  const wake = await context.newPage();
  try {
    const waiting = context.waitForEvent('serviceworker', { timeout: 10_000 });
    await wake.goto(`chrome-extension://${EXT_IDS.get(context)}/popup/popup.html`);
    worker = await waiting;
  } finally {
    await wake.close();
  }
  return worker;
}

// The tab the user is looking at: brought to the front, then asked for as the active tab
// (never matched by URL).
async function activeTabId(page) {
  const worker = await serviceWorker(page.context());
  await page.bringToFront();
  const id = await worker.evaluate(async () => {
    const [t] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
    return t ? t.id : null;
  });
  if (id == null) throw new Error('no active tab');
  return id;
}

export async function launch({ fallback = true, helper = true } = {}) {
  const work = mkdtempSync(path.join(tmpBase(), 'jaf-e2e-'));
  const home = path.join(work, 'home');
  mkdirSync(home, { recursive: true, mode: 0o700 });
  const cleanups = [() => rmSync(work, { recursive: true, force: true })];
  const unwind = async () => {
    for (const fn of cleanups) {
      try { await fn(); } catch (_) { /* best effort */ }
    }
  };

  try {
    const [a, b] = await Promise.all([startStatic(FIXTURES), startStatic(FIXTURES)]);
    for (const s of [a, b]) cleanups.unshift(() => new Promise((r) => s.server.close(r)));
    const ports = { A: a.port, B: b.port };

    let provider = null;
    let helperInfo = null;
    if (helper) {
      provider = await startProvider();
      cleanups.unshift(() => killProc(provider.proc));
      helperInfo = await startHelper(home, provider);
      cleanups.unshift(() => killProc(helperInfo.proc));
    }

    const context = await chromium.launchPersistentContext(path.join(work, 'profile'), {
      channel: 'chromium',
      headless: true,
      args: [`--disable-extensions-except=${EXTENSION}`, `--load-extension=${EXTENSION}`],
    });
    cleanups.unshift(() => context.close());
    let [worker] = context.serviceWorkers();
    worker ||= await context.waitForEvent('serviceworker', { timeout: 15_000 });
    const extId = new URL(worker.url()).host;
    EXT_IDS.set(context, extId);
    // The extension finds the helper on the default port; the tests' helper uses a free one.
    const local = {};
    if (helperInfo) local.port = helperInfo.port;
    if (fallback === false) local.prefs = { fallback: false };
    if (Object.keys(local).length) await worker.evaluate((v) => chrome.storage.local.set(v), local);
    const page = context.pages()[0] ?? (await context.newPage());
    const popupUrl = (tabId) => `chrome-extension://${extId}/popup/popup.html${tabId == null ? '' : `?tab=${tabId}`}`;

    return {
      context,
      extId,
      page,
      worker,
      popupUrl,
      helper: helperInfo && {
        port: helperInfo.port,
        token: helperInfo.token,
        home,
        output: helperInfo.output,
        stop: () => killProc(helperInfo.proc),
        // Fake keychain: a JSON file keyed by Keychain service name.
        setKey: (name, key) => writeFileSync(
          path.join(home, 'keychain.json'),
          JSON.stringify({ ...readKeychain(home), [`job-autofill-${name}`]: key }),
          { mode: 0o600 },
        ),
      },
      provider: provider && { port: provider.port, requests: provider.requests, setMode: provider.setMode },
      fixtureUrl: (name, port = 'A') => `http://127.0.0.1:${ports[port]}/${name}`,
      // Pairs the extension with the started helper through the same message the popup sends.
      async pair() {
        const p = await context.newPage();
        try {
          await p.goto(popupUrl());
          const res = await p.evaluate((t) => chrome.runtime.sendMessage({ type: 'PAIR', token: t }), helperInfo.token);
          if (!res || !res.ok) throw new Error(`pair failed: ${JSON.stringify(res)}`);
        } finally {
          await p.close();
        }
      },
      async close() {
        await unwind();
      },
    };
  } catch (e) {
    await unwind();
    throw e;
  }
}

function readKeychain(home) {
  try { return JSON.parse(readFileSync(path.join(home, 'keychain.json'), 'utf8')); } catch (_) { return {}; }
}

// Opens the popup for `page`'s tab (as the active tab, not by URL) in its own tab and returns it.
export async function openPopup(page) {
  const tabId = await activeTabId(page);
  const context = page.context();
  const popup = await context.newPage();
  await popup.goto(`chrome-extension://${EXT_IDS.get(context)}/popup/popup.html?tab=${tabId}`);
  return { popup, tabId };
}

// A stand-in for the content script, injected into the page's top frame (extension isolated
// world). It records every START and, when `report` is given, answers it with a REPORT.
export async function stubContent(page, { report = null } = {}) {
  const tabId = await activeTabId(page);
  const worker = await serviceWorker(page.context());
  await worker.evaluate(async ({ tabId, report }) => {
    await chrome.scripting.executeScript({
      target: { tabId },
      args: [report],
      func: (report) => {
        if (globalThis.__afStub) return;
        globalThis.__afStub = { starts: [] };
        chrome.runtime.onMessage.addListener((m) => {
          if (!m || m.type !== 'START') return;
          globalThis.__afStub.starts.push(m);
          if (report) chrome.runtime.sendMessage({ type: 'REPORT', summary: { runId: m.runId, ...report } });
        });
      },
    });
  }, { tabId, report });
  return {
    tabId,
    starts: () => worker.evaluate(async ({ tabId }) => {
      const [r] = await chrome.scripting.executeScript({ target: { tabId }, func: () => (globalThis.__afStub ? globalThis.__afStub.starts : []) });
      return r.result;
    }, { tabId }),
  };
}

// Opens the popup for `page`'s tab, optionally turns on "Continue and submit when safe",
// clicks "Autofill page" and waits until the run settles (its status in chrome.storage.session
// is no longer 'running'), or until the popup shows why no run started. Returns
// `{ tabId, text, run, status, reason, step, counts }`; `text` is the popup's visible text.
export async function runAutofill(page, { submit = false, timeout = 30_000 } = {}) {
  const { popup, tabId } = await openPopup(page);
  try {
    const run = popup.getByRole('button', { name: 'Autofill page' });
    await run.waitFor({ state: 'visible', timeout: 10_000 });
    const readRun = () => popup.evaluate(async (id) => ((await chrome.storage.session.get('runs')).runs || {})[id] || null, tabId);
    const before = await readRun();
    if (submit) await popup.getByRole('switch', { name: /Continue and submit when safe/ }).click();
    await run.click();

    const end = Date.now() + timeout;
    let current = null;
    let failure = '';
    while (Date.now() < end) {
      current = await readRun();
      if (current && (!before || current.runId !== before.runId) && current.status !== 'running') break;
      failure = await popup.evaluate(() => { const m = document.getElementById('run-msg'); return m.classList.contains('err') ? m.textContent : ''; });
      if (failure && !(current && (!before || current.runId !== before.runId))) break;
      current = null;
      await popup.waitForTimeout(100);
    }
    if (!current && !failure) throw new Error(`runAutofill: run did not settle within ${timeout} ms`);
    // The popup re-renders from the storage change; wait for the run button to come back.
    if (current) await popup.locator('#run:not([disabled])').waitFor({ timeout: 5_000 }).catch(() => {});
    const text = await popup.locator('body').innerText();
    return {
      tabId,
      text,
      run: current,
      status: current ? current.status : 'error',
      reason: current ? current.reason : failure,
      step: current ? current.step : 0,
      counts: current ? current.counts : null,
    };
  } finally {
    await popup.close();
  }
}
