// Service worker: talks to the local helper, keeps the synced profile and resume in
// chrome.storage.local, starts runs and keeps per-tab run state in chrome.storage.session
// (the worker sleeps after ~30 s idle, so nothing important lives in memory).
//
// Messages (all handlers are registered synchronously, as MV3 requires):
//   popup -> bg   RUN {tabId, submit} | SYNC | PAIR {token} | SAVE_PROFILE {manual}
//                 SAVE_CONFIG {patch, fallback?} | MODELS {provider}
//   content -> bg DRAFT {req} | REPORT {tabId?, summary} | DEBUGGER_FILL {frameId, selector, kind, value}
//                 LOG_RUN {rec}
//   bg -> content START {runId, profile, resumeRef, submit, fallback}
//
// REPORT summary: {runId?, status, reason?, step?, counts?: {green, yellow, ai_drafts, ai_calls, fields}}
//   status: 'running' | 'filled' | 'stopped' | 'submitted_confirmed' | 'submitted_unconfirmed' | 'error'
//   `fields` is the number of fillable controls the content script found (0 -> "No form fields").
'use strict';

const DEFAULT_PORT = 8766;
const OFFLINE_DRAFT = "AutoFill: Helper offline \u2014 AI drafts unavailable";
const CANT_FILL = "Can't fill this page";
const NEEDS_SYNC = 'Autofill needs one sync with the helper first.';
const RUN_STATUSES = ['running', 'filled', 'stopped', 'submitted_confirmed', 'submitted_unconfirmed', 'error'];

// Content scripts read run state from chrome.storage.session (wizard steps, panel counts).
chrome.storage.session.setAccessLevel({ accessLevel: 'TRUSTED_AND_UNTRUSTED_CONTEXTS' }).catch(() => {});

// ---- helper client -------------------------------------------------------------------
async function helperBase() {
  const { token, port } = await chrome.storage.local.get(['token', 'port']);
  return { token, base: `http://127.0.0.1:${port || DEFAULT_PORT}`, port: port || DEFAULT_PORT };
}

// Resolves to {offline:true} (no answer), {unpaired:true}, or {status, data, res}.
// Domain errors come back as HTTP 200 with {error}: callers read `data.error`.
async function helperCall(method, path, body, timeoutMs = 8000) {
  const { token, base } = await helperBase();
  if (!token) return { unpaired: true };
  const headers = { 'X-Job-Autofill-Token': token };
  // Chrome sends no Origin header on GETs from an extension with host permission, and the
  // helper refuses requests without one, so reads go as POST + a method-override header.
  if (method === 'GET') { method = 'POST'; headers['X-HTTP-Method-Override'] = 'GET'; }
  const init = { method, headers, signal: AbortSignal.timeout(timeoutMs) };
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(base + path, init);
  } catch (_) {
    return { offline: true };
  }
  if (path === '/resume.pdf' && res.ok) return { status: res.status, res };
  let data = null;
  try { data = await res.json(); } catch (_) { /* empty body (403) */ }
  return { status: res.status, data, res };
}

function toBase64(buf) {
  const bytes = new Uint8Array(buf);
  let s = '';
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  return btoa(s);
}

// Caches the resume bytes. A 404 from the helper clears the cache and records the reason;
// a helper that cannot be reached keeps whatever was cached.
async function syncResume() {
  const r = await helperCall('GET', '/resume.pdf', undefined, 15000);
  if (r.offline || r.unpaired) return;
  if (r.status === 200) {
    const buf = await r.res.arrayBuffer();
    let name = 'resume.pdf';
    try { name = decodeURIComponent(r.res.headers.get('X-Resume-Name') || name); } catch (_) { /* keep default */ }
    await chrome.storage.local.set({
      resume: { name, type: 'application/pdf', b64: toBase64(buf), size: buf.byteLength },
      resumeError: '',
    });
  } else {
    await chrome.storage.local.remove('resume');
    await chrome.storage.local.set({ resumeError: (r.data && r.data.error) || 'AutoFill: Resume file not found \u2014 pick it in Profile' });
  }
}

// -> {status: 'ok' | 'offline' | 'rejected' | 'unpaired'}
async function sync() {
  const prof = await helperCall('GET', '/profile');
  if (prof.unpaired) return { status: 'unpaired' };
  if (prof.offline) return { status: 'offline' };
  if (prof.status === 403) return { status: 'rejected' };
  if (prof.status !== 200 || !prof.data) return { status: 'offline' };
  const cfg = await helperCall('GET', '/config');
  const patch = { profile: prof.data, syncedAt: new Date().toISOString() };
  if (cfg.status === 200 && cfg.data) patch.config = cfg.data;
  await chrome.storage.local.set(patch);
  await syncResume();
  return { status: 'ok' };
}

async function pair(token) {
  token = String(token || '').trim();
  if (!token) return { error: 'Paste the token the helper printed.' };
  const prev = (await chrome.storage.local.get('token')).token;
  await chrome.storage.local.set({ token });
  const r = await helperCall('GET', '/health');
  if (r.offline) {
    await restoreToken(prev);
    const { port } = await helperBase();
    return { error: `Helper not reachable at 127.0.0.1:${port} \u2014 start it first.` };
  }
  if (r.status !== 200) {
    await restoreToken(prev);
    return { error: 'The helper rejected that token. Copy the one it printed (or run: python3 job-autofill/helper/server.py pair).' };
  }
  await sync();
  return { ok: true };
}

async function restoreToken(prev) {
  if (prev) await chrome.storage.local.set({ token: prev });
  else await chrome.storage.local.remove('token');
}

async function saveProfile(manual) {
  const r = await helperCall('PUT', '/profile', { manual });
  if (r.offline) return { error: 'Helper offline \u2014 profile not saved.' };
  if (r.status !== 200 || !r.data) return { error: (r.data && r.data.error) || `Helper refused the profile (${r.status}).` };
  await chrome.storage.local.set({ profile: r.data });
  return { ok: true, profile: r.data };
}

async function saveConfig(patch, fallback) {
  if (fallback !== undefined) {
    const { prefs } = await chrome.storage.local.get('prefs');
    await chrome.storage.local.set({ prefs: Object.assign({}, prefs, { fallback: !!fallback }) });
  }
  if (patch && Object.keys(patch).length) {
    const r = await helperCall('PUT', '/config', patch);
    if (r.offline) return { error: 'Helper offline \u2014 settings not saved.' };
    if (r.status !== 200 || !r.data) return { error: (r.data && r.data.error) || `Helper refused the settings (${r.status}).` };
    await chrome.storage.local.set({ config: r.data });
    return { ok: true, config: r.data };
  }
  return { ok: true };
}

async function listModels(provider) {
  const r = await helperCall('GET', '/models?provider=' + encodeURIComponent(provider), undefined, 30000);
  if (r.offline) return { offline: true };
  if (r.unpaired) return { error: 'Not paired' };
  if (r.status !== 200 || !r.data) return { error: `Helper refused the request (${r.status}).` };
  return r.data.error ? { error: r.data.error } : { models: r.data.models || [] };
}

// ---- run state (chrome.storage.session) -----------------------------------------------
let runsQueue = Promise.resolve();
// Serialises read-modify-write on `runs` so concurrent REPORTs cannot lose each other's update.
function mutateRuns(fn) {
  const next = runsQueue.then(async () => {
    const { runs } = await chrome.storage.session.get('runs');
    const all = runs || {};
    const out = fn(all);
    await chrome.storage.session.set({ runs: all });
    return out;
  });
  runsQueue = next.catch(() => {});
  return next;
}

function fillable(url) {
  let u;
  try { u = new URL(url || ''); } catch (_) { return false; }
  if (u.protocol !== 'http:' && u.protocol !== 'https:') return false;
  if (/\.pdf$/i.test(u.pathname)) return false;
  if (u.hostname === 'chromewebstore.google.com') return false;
  if (u.hostname === 'chrome.google.com' && u.pathname.startsWith('/webstore')) return false;
  return true;
}

function flatProfile(p) {
  return Object.assign({}, p.imported || {}, p.manual || {});
}

async function sendStart(tabId, msg) {
  try {
    await chrome.tabs.sendMessage(tabId, msg);
    return true;
  } catch (_) { /* no content script in the page (opened before install, or not allowed) */ }
  try {
    const files = chrome.runtime.getManifest().content_scripts[0].js;
    await chrome.scripting.executeScript({ target: { tabId, allFrames: true }, files });
    await chrome.tabs.sendMessage(tabId, msg);
    return true;
  } catch (_) {
    return false;
  }
}

async function startRun({ tabId, submit }) {
  let tab;
  try { tab = await chrome.tabs.get(tabId); } catch (_) { return { error: CANT_FILL }; }
  if (!fillable(tab.url)) return { error: CANT_FILL };
  const { token } = await chrome.storage.local.get('token');
  if (!token) return { error: 'Not paired with the helper.' };

  const syncResult = await sync(); // Offline runs may use cache; rejected credentials must not.
  if (syncResult.status === 'rejected' || syncResult.status === 'unpaired') return { error: 'Not paired with the helper.' };
  const st = await chrome.storage.local.get(['profile', 'resume', 'prefs', 'syncedAt']);
  if (!st.profile || !st.syncedAt) return { error: NEEDS_SYNC };

  const runId = crypto.randomUUID();
  const frameIds = (await chrome.scripting.executeScript({ target: { tabId, allFrames: true }, func: () => true })).map(r => r.frameId);
  const now = Date.now();
  await mutateRuns((all) => {
    const prev = all[tabId];
    all[tabId] = {
      runId,
      submit: !!submit,
      step: 0,
      fingerprints: [],
      frames: {},
      frameIds,
      path: new URL(tab.url).pathname,
      sourceHostname: new URL(tab.url).hostname,
      url: tab.url,
      counts: { green: 0, yellow: 0, filled: 0, ai_drafts: 0, ai_calls: 0, fields: null },
      status: 'running',
      reason: '',
      submittedUrls: prev && Array.isArray(prev.submittedUrls) ? prev.submittedUrls : [],
      host: new URL(tab.url).host,
      startedAt: now,
      updatedAt: now,
    };
  });

  const resumeRef = st.resume ? { name: st.resume.name, type: st.resume.type, size: st.resume.size } : null;
  const ok = await sendStart(tabId, {
    type: 'START',
    runId,
    profile: flatProfile(st.profile),
    resumeRef,
    submit: !!submit,
    fallback: !(st.prefs && st.prefs.fallback === false),
  });
  if (!ok) {
    await mutateRuns((all) => {
      if (all[tabId] && all[tabId].runId === runId) {
        Object.assign(all[tabId], { status: 'error', reason: CANT_FILL, updatedAt: Date.now() });
      }
    });
    return { error: CANT_FILL };
  }
  return { ok: true, runId };
}

function applyReport(tabId, summary, frameId = 0) {
  return mutateRuns((all) => {
    const run = all[tabId];
    if (!run || !summary || (summary.runId && summary.runId !== run.runId)) return false;
    if (RUN_STATUSES.includes(summary.status)) run.status = summary.status;
    if (typeof summary.ats === 'string') run.ats = summary.ats;
    if (typeof summary.reason === 'string') run.reason = summary.reason;
    if (Number.isInteger(summary.step)) run.step = Math.max(run.step || 0, summary.step);
    if (summary.counts && typeof summary.counts === 'object') {
      run.frames ||= {};
      run.frames[frameId] = Object.assign({}, run.frames[frameId], summary.counts);
      run.counts = { green: 0, yellow: 0, filled: 0, ai_drafts: 0, ai_calls: 0, fields: 0 };
      for (const counts of Object.values(run.frames)) {
        for (const key of Object.keys(run.counts)) {
          if (Number.isFinite(counts[key]) && counts[key] >= 0) run.counts[key] += counts[key];
        }
      }
    }
    run.updatedAt = Date.now();
    return true;
  });
}

// ---- debugger fallback ----------------------------------------------------------------
const debuggerQueues = new Map();
// One attach at a time per tab; always detach, even on failure.
function withDebugger(tabId, fn) {
  const prev = debuggerQueues.get(tabId) || Promise.resolve();
  const next = prev.catch(() => {}).then(async () => {
    const target = { tabId };
    await chrome.debugger.attach(target, '1.3');
    try {
      return await fn((method, params) => chrome.debugger.sendCommand(target, method, params));
    } finally {
      await chrome.debugger.detach(target).catch(() => {});
    }
  });
  debuggerQueues.set(tabId, next.catch(() => {}));
  return next;
}

// Focuses the element inside its frame and returns where its centre is (viewport pixels).
function focusInFrame(selector, selectText) {
  const el = document.querySelector(selector);
  if (!el) return null;
  el.scrollIntoView({ block: 'center', inline: 'center' });
  el.focus();
  if (selectText) {
    if (typeof el.select === 'function') el.select();
    else if (el.isContentEditable) document.getSelection().selectAllChildren(el);
  }
  const r = el.getBoundingClientRect();
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
}

// kind 'text': focus, select the old value, insert `value` as real input.
// kind 'click': real mouse click at the element's centre (top frame only).
async function debuggerFill(tabId, { frameId = 0, selector, kind, value }) {
  if (typeof selector !== 'string' || !selector) return { error: 'selector required' };
  if (kind !== 'text' && kind !== 'click') return { error: `unknown kind ${kind}` };
  if (kind === 'click' && frameId !== 0) return { error: 'Real clicks inside frames are not supported' };
  const [found] = await chrome.scripting.executeScript({
    target: { tabId, frameIds: [frameId] },
    func: focusInFrame,
    args: [selector, kind === 'text'],
  });
  const at = found && found.result;
  if (!at) return { error: 'element not found' };
  try {
    await withDebugger(tabId, async (send) => {
      if (kind === 'text') {
        await send('Input.insertText', { text: String(value == null ? '' : value) });
      } else {
        for (const type of ['mousePressed', 'mouseReleased']) {
          await send('Input.dispatchMouseEvent', { type, x: at.x, y: at.y, button: 'left', clickCount: 1 });
        }
      }
    });
  } catch (e) {
    return { error: `debugger: ${e && e.message ? e.message : e}` };
  }
  return { ok: true };
}

// ---- drafts and run log (content -> helper) --------------------------------------------
async function draft(req) {
  const r = await helperCall('POST', '/draft', req, 45000);
  if (r.offline || r.unpaired) return { error: OFFLINE_DRAFT };
  if (r.status === 403) return { error: 'AutoFill: Helper rejected the token \u2014 pair again' };
  if (r.status !== 200 || !r.data) return { error: `AutoFill: Helper error (${r.status})` };
  return r.data;
}

async function logRun(rec) {
  const r = await helperCall('POST', '/runs', rec);
  return r.status === 200 ? { ok: true } : { error: 'run log not written' };
}

async function runState(tabId, runId) {
  await runsQueue;
  const { runs = {} } = await chrome.storage.session.get('runs');
  const run = runs[tabId];
  return run && (!runId || run.runId === runId) ? run : null;
}

async function pageState(tabId, runId) {
  const run = await runState(tabId, runId);
  if (!run || !run.frameIds.every(id => run.frames[id])) return { ready: false };
  const snapshots = await chrome.scripting.executeScript({
    target: { tabId, allFrames: true },
    func: () => globalThis.AF?.pageSafety?.() || { captcha: '', yellow: 0, required: 0, readback: 0, aiDrafts: 0, button: '' },
  });
  const safety = { captcha: '', yellow: 0, required: 0, readback: 0, aiDrafts: 0, button: false, submitted: run.submittedUrls.includes(run.url) };
  let action = null;
  for (const { frameId, result } of snapshots) {
    safety.captcha ||= result.captcha;
    for (const key of ['yellow', 'required', 'readback', 'aiDrafts']) safety[key] += result[key] || 0;
    if (result.button && !action) action = { frameId, kind: result.button };
  }
  safety.button = !!action;
  return { ready: true, safety, action };
}

async function finishRun(tabId, msg) {
  const rec = await mutateRuns(all => {
    const run = all[tabId];
    if (!run || run.runId !== msg.runId || run.logged) return null;
    run.status = msg.status;
    run.reason = msg.reason || '';
    run.pendingSubmit = false;
    run.logged = true;
    const c = run.counts;
    return { host: run.host, path: run.path, ats: run.ats || 'generic', green: c.green, yellow: c.yellow,
      ai_drafts: c.ai_drafts, ai_calls: c.ai_calls, steps: run.step,
      outcome: msg.status === 'stopped' ? `stopped:${msg.code || 'stopped'}` : msg.status };
  });
  return rec ? logRun(rec) : { ok: true };
}

async function safeAction(tabId, runId) {
  const state = await pageState(tabId, runId);
  const check = (await chrome.scripting.executeScript({
    target: { tabId, frameIds: [0] }, args: [state.safety],
    func: safety => globalThis.AF.safetyCheck(safety),
  }))[0].result;
  if (!check.ok) return { error: check.reason, code: check.code };
  const claimed = await mutateRuns(all => {
    const run = all[tabId];
    if (!run || run.runId !== runId || run.pendingSubmit || run.logged || !run.submit) return false;
    if (state.action.kind === 'submit') {
      if (run.submittedUrls.includes(run.url)) return false;
      run.submittedUrls.push(run.url);
      run.pendingSubmit = true;
      run.submitDeadline = Date.now() + 15000;
    }
    return { deadline: run.submitDeadline };
  });
  if (!claimed) return { error: 'Already submitted from this tab', code: 'duplicate' };
  if (state.action.kind === 'submit') setTimeout(() => {
    finishRun(tabId, { runId, status: 'submitted_unconfirmed' }).catch(() => {});
  }, Math.max(0, claimed.deadline - Date.now()));
  await chrome.tabs.sendMessage(tabId, { type: 'SAFE_CLICK', runId }, { frameId: state.action.frameId });
  return { kind: state.action.kind, deadline: claimed.deadline };
}

// ---- message routing --------------------------------------------------------------------
const POPUP_ONLY = new Set(['RUN', 'SYNC', 'PAIR', 'SAVE_PROFILE', 'SAVE_CONFIG', 'MODELS']);

function fromExtensionPage(sender) {
  return sender.id === chrome.runtime.id && typeof sender.url === 'string'
    && sender.url.startsWith(chrome.runtime.getURL(''));
}

async function handle(msg, sender) {
  if (!msg || typeof msg.type !== 'string') return { error: 'bad message' };
  const trusted = fromExtensionPage(sender);
  if (POPUP_ONLY.has(msg.type) && !trusted) return { error: 'not allowed' };
  // A content script's tab is the sender's; extension pages (popup, tests) name the tab.
  const tabId = !trusted && sender.tab ? sender.tab.id : msg.tabId;
  switch (msg.type) {
    case 'RUN': return startRun({ tabId: msg.tabId, submit: !!msg.submit });
    case 'SYNC': return sync();
    case 'PAIR': return pair(msg.token);
    case 'SAVE_PROFILE': return saveProfile(msg.manual);
    case 'SAVE_CONFIG': return saveConfig(msg.patch, msg.fallback);
    case 'MODELS': return listModels(msg.provider);
    case 'DRAFT': return draft(msg.req);
    case 'RUN_STATE': return runState(tabId);
    case 'PAGE_STATE': return pageState(tabId, msg.runId);
    case 'SAFE_ACTION': return safeAction(tabId, msg.runId);
    case 'REPORT': return { ok: await applyReport(tabId, msg.summary, trusted ? 0 : sender.frameId || 0) };
    case 'LOG_RUN': return finishRun(tabId, msg);
    case 'DEBUGGER_FILL': return debuggerFill(tabId, { ...msg, frameId: trusted ? msg.frameId || 0 : sender.frameId || 0 });
    default: return { error: `unknown message ${msg.type}` };
  }
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  handle(msg, sender).then(sendResponse, (e) => sendResponse({ error: String((e && e.message) || e) }));
  return true;
});

// A closed tab's run state is dropped.
chrome.tabs.onRemoved.addListener((tabId) => {
  mutateRuns((all) => { delete all[tabId]; }).catch(() => {});
});
