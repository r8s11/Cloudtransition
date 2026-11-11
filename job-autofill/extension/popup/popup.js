// Popup: Run / Profile / AI tabs. Talks to background.js by message; reads cached state
// from chrome.storage.local and per-tab run state from chrome.storage.session.
// Nothing here is persisted for the submit switch: it always starts off (U17).
'use strict';

const $ = (id) => document.getElementById(id);
const DEFAULT_PORT = 8766;
const STALE_RUN_MS = 60_000; // a "running" run with no report for this long no longer blocks the button
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const LONG_SUBMIT_HINT = "This run only. Clicks Next or Submit only when there's no CAPTCHA, nothing to review, no empty required field and every value checked on the page.";
const PROVIDER_NAMES = { anthropic: 'Anthropic', openai: 'OpenAI' };

const MANUAL_SELECTS = {
  workAuthorization: ['Yes', 'No'],
  needsSponsorship: ['Yes', 'No'],
  gender: ['Male', 'Female', 'Non-binary', 'Decline to self-identify'],
  race: ['American Indian or Alaska Native', 'Asian', 'Black or African American', 'Hispanic or Latino',
    'Native Hawaiian or Other Pacific Islander', 'White', 'Two or more races', 'Decline to self-identify'],
  veteran: ['Protected veteran', 'Not a protected veteran', 'Decline to self-identify'],
  disability: ['Yes, I have a disability', 'No, I do not have a disability', 'Decline to self-identify'],
};
const MANUAL_TEXT = { street: 'm-street', zip: 'm-zip', country: 'm-country' };

let tab = null;           // the tab this popup acts on
let local = {};           // chrome.storage.local snapshot
let runs = {};            // chrome.storage.session.runs
let syncStatus = 'checking'; // 'checking' | 'ok' | 'offline' | 'rejected'
let submitOn = false;
let startError = '';
let modelsToken = 0;

const send = (msg) => chrome.runtime.sendMessage(msg);

function fmtDate(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getDate()} ${MONTHS[d.getMonth()]}, ${p(d.getHours())}:${p(d.getMinutes())}`;
}

function fillable(url) {
  let u;
  try { u = new URL(url || ''); } catch (_) { return false; }
  if (u.protocol !== 'http:' && u.protocol !== 'https:') return false;
  if (/\.pdf$/i.test(u.pathname)) return false;
  if (u.hostname === 'chromewebstore.google.com') return false;
  return !(u.hostname === 'chrome.google.com' && u.pathname.startsWith('/webstore'));
}

function setText(el, text) { el.textContent = text; }
function show(el, on) { el.hidden = !on; }

async function resolveTab() {
  const wanted = Number(new URLSearchParams(location.search).get('tab'));
  try {
    if (wanted) return await chrome.tabs.get(wanted);
    const [t] = await chrome.tabs.query({ active: true, currentWindow: true });
    return t || null;
  } catch (_) {
    return null;
  }
}

async function refresh() {
  local = await chrome.storage.local.get(null);
  runs = (await chrome.storage.session.get('runs')).runs || {};
}

// ---- header and views ------------------------------------------------------------------
function renderHeader() {
  const dot = $('dot');
  const port = local.port || DEFAULT_PORT;
  let cls = 'off';
  let text = 'Not paired';
  if (local.token && syncStatus !== 'rejected') {
    if (syncStatus === 'ok') { cls = 'on'; text = `Helper connected · 127.0.0.1:${port}`; }
    else if (syncStatus === 'offline') { cls = 'warn'; text = 'Helper offline'; }
    else { cls = 'warn'; text = 'Checking helper…'; }
  }
  dot.className = 'dot ' + cls;
  setText($('status-text'), text);
}

function renderViews() {
  const paired = !!local.token && syncStatus !== 'rejected';
  show($('view-pair'), !paired);
  show($('view-main'), paired);
  if (!paired) {
    $('pair-hint').textContent = syncStatus === 'rejected'
      ? 'The helper rejected the saved token. Paste the one it printed (or run: python3 job-autofill/helper/server.py pair):'
      : 'Not paired with the helper. Start it, then paste the token it printed:';
  }
}

// ---- Run tab ---------------------------------------------------------------------------
function activeRun() {
  const run = tab && runs[tab.id];
  return run && run.status === 'running' && Date.now() - (run.updatedAt || 0) < STALE_RUN_MS ? run : null;
}

function renderRun() {
  const run = tab ? runs[tab.id] : null;
  const active = activeRun();
  const canFill = !!tab && fillable(tab.url);
  const hasCache = !!local.profile && !!local.syncedAt;
  const offline = syncStatus === 'offline';

  const line = $('offline-line');
  show(line, offline && hasCache);
  if (offline && hasCache) setText(line, `Helper offline — profile from last sync (${fmtDate(local.syncedAt)}); AI drafts unavailable`);

  const runBtn = $('run');
  if (active) {
    setText(runBtn, `Filling…${active.step > 1 ? ' step ' + active.step : ''}`);
    runBtn.disabled = true;
  } else {
    setText(runBtn, 'Autofill page');
    runBtn.disabled = !(canFill && hasCache);
  }

  const sw = $('submit');
  const on = active ? !!active.submit : submitOn;
  sw.setAttribute('aria-checked', String(on));
  sw.setAttribute('aria-disabled', String(!!active));
  setText($('submit-hint'), active && active.submit
    ? 'On for this run. Turns off when the run ends.'
    : (offline && hasCache ? 'This run only.' : LONG_SUBMIT_HINT));

  renderRunCard(run, active, canFill, hasCache);
}

function renderRunCard(run, active, canFill, hasCache) {
  const card = $('run-card');
  const msg = $('run-msg');
  msg.className = 'msg';
  show($('run-card-hint'), false);
  const counts = (run && run.counts) || {};
  const green = counts.green || 0;
  const yellow = counts.yellow || 0;
  const filled = counts.filled || 0;
  const aiDrafts = counts.ai_drafts || 0;
  const noFields = run && !active && counts.fields === 0 && run.status !== 'error';

  show(card, !!run && !noFields);
  if (run && !noFields) {
    setText($('run-card-title'), `${active ? 'Running' : 'Last run'} · ${run.host || ''}`);
    setText($('run-card-line'), active
      ? `Step ${Math.max(run.step, 1)} of ? · ${filled} filled so far`
      : `Filled ${filled} · ${yellow} to review`);
    const pills = $('run-card-counts');
    pills.textContent = '';
    const pill = (cls, text) => { const s = document.createElement('span'); s.className = 'pill ' + cls; s.textContent = text; pills.appendChild(s); };
    if (active) pill('ok', `✓ ${filled}`);
    else {
      pill('ok', `✓ ${green} from profile`);
      if (yellow) pill('rv', `! ${yellow} to review`);
      if (aiDrafts) pill('ai', `AI ${aiDrafts} draft${aiDrafts === 1 ? '' : 's'}`);
    }
    const hint = $('run-card-hint');
    if (!active && run.status === 'filled') {
      setText(hint, yellow
        ? `Not submitted — review the yellow field${yellow === 1 ? '' : 's'}, then submit yourself.`
        : 'Not submitted — check the page, then submit yourself.');
      show(hint, true);
    } else if (!active && run.status === 'stopped') {
      setText(hint, 'Not submitted — finish on the page yourself.');
      show(hint, true);
    }
  }

  let text = '';
  if (!canFill) { text = "Can't fill this page"; msg.classList.add('err'); }
  else if (startError) { text = startError; msg.classList.add('err'); }
  else if (!hasCache) { text = 'Autofill needs one sync with the helper first.'; }
  else if (noFields) { text = 'No form fields found on this page'; }
  else if (active) { text = counts.fields == null ? 'Filling this page…' : 'Waiting for the next step…'; }
  else if (run && run.status === 'filled') { text = `Filled ${filled} · ${yellow} to review`; msg.classList.add('ok'); }
  else if (run && run.status === 'stopped') { text = `Stopped: ${run.reason}`; msg.classList.add('err'); }
  else if (run && run.status === 'submitted_confirmed') { text = 'Submitted · confirmed'; msg.classList.add('ok'); }
  else if (run && run.status === 'submitted_unconfirmed') { text = 'Submitted · not confirmed — check the page before trying again'; msg.classList.add('err'); }
  else if (run && run.status === 'error') { text = run.reason || "Can't fill this page"; msg.classList.add('err'); }
  setText(msg, text);
}

async function onRun() {
  startError = '';
  const submit = submitOn;
  submitOn = false;
  $('run').disabled = true;
  const res = await send({ type: 'RUN', tabId: tab.id, submit });
  if (res && res.error) startError = res.error;
  await refresh();
  renderRun();
}

// ---- Profile tab -----------------------------------------------------------------------
function fillSelect(sel, options, current) {
  sel.textContent = '';
  const add = (value, label) => { const o = document.createElement('option'); o.value = value; o.textContent = label; sel.appendChild(o); };
  add('', 'Leave blank');
  const all = current && !options.includes(current) ? options.concat([current]) : options;
  for (const o of all) add(o, o);
  sel.value = current || '';
}

function stripUrl(u) { return String(u).replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, ''); }

function formatSize(bytes) { return `${Math.max(1, Math.round(bytes / 1024))} KB`; }

function renderProfile() {
  const p = local.profile;
  if (!p) return;
  const imp = p.imported || {};
  const man = p.manual || {};
  setText($('profile-src'), `From resume/master.md · read-only${local.syncedAt ? ' · synced ' + fmtDate(local.syncedAt) : ''}`);
  $('p-first').value = imp.firstName || '';
  $('p-last').value = imp.lastName || '';
  $('p-email').value = imp.email || '';
  $('p-phone').value = imp.phone || '';
  $('p-city').value = [imp.city, imp.state].filter(Boolean).join(', ');
  const links = [imp.linkedin, imp.github, imp.website].filter(Boolean);
  $('p-links').value = links.length ? stripUrl(links[0]) + (links.length > 1 ? ` · +${links.length - 1}` : '') : '';
  $('p-links').title = links.map(stripUrl).join('\n');

  for (const [key, id] of Object.entries(MANUAL_TEXT)) $(id).value = man[key] || '';
  for (const [key, options] of Object.entries(MANUAL_SELECTS)) fillSelect($('m-' + key), options, man[key] || '');

  const err = $('profile-error');
  show(err, !!p.error);
  setText(err, p.error || '');
  const missing = Array.isArray(p.missing) ? p.missing : [];
  show($('profile-missing'), missing.length > 0);
  setText($('profile-missing'), `Not found in resume/master.md: ${missing.join(', ')}`);
  show($('profile-hint'), missing.length > 0 || !!p.error || !!local.resumeError);
  renderResume();
}

function renderResume() {
  const path = local.config && local.config.resume_pdf;
  const r = local.resume;
  const label = path || (r && r.name) || 'No file chosen';
  setText($('resume-text'), r && r.size ? `${label} · ${formatSize(r.size)}` : label);
  const err = $('resume-error');
  show(err, !!local.resumeError);
  setText(err, local.resumeError || '');
}

async function onSaveProfile() {
  const manual = {};
  for (const [key, id] of Object.entries(MANUAL_TEXT)) manual[key] = $(id).value.trim();
  for (const key of Object.keys(MANUAL_SELECTS)) manual[key] = $('m-' + key).value;
  const msg = $('profile-msg');
  msg.className = 'msg';
  setText(msg, 'Saving…');
  const res = await send({ type: 'SAVE_PROFILE', manual });
  if (res && res.ok) { msg.classList.add('ok'); setText(msg, 'Profile saved'); await refresh(); }
  else { msg.classList.add('err'); setText(msg, (res && res.error) || 'Profile not saved'); }
}

async function onSetResume() {
  const path = $('resume-path').value.trim();
  const msg = $('profile-msg');
  msg.className = 'msg';
  if (!path) { msg.classList.add('err'); setText(msg, 'Enter the path to your resume PDF.'); return; }
  setText(msg, 'Checking the file…');
  const saved = await send({ type: 'SAVE_CONFIG', patch: { resume_pdf: path } });
  if (!saved || !saved.ok) { msg.classList.add('err'); setText(msg, (saved && saved.error) || 'Not saved'); return; }
  await send({ type: 'SYNC' });
  await refresh();
  renderResume();
  if (local.resumeError) setText(msg, '');
  else { msg.classList.add('ok'); setText(msg, 'Resume file saved'); show($('resume-edit'), false); $('resume-change').setAttribute('aria-expanded', 'false'); }
}

// ---- AI tab ----------------------------------------------------------------------------
function currentProvider() {
  return document.querySelector('input[name="provider"]:checked').value;
}

function renderAi() {
  const cfg = local.config || {};
  const provider = cfg.provider === 'openai' ? 'openai' : 'anthropic';
  $('prov-' + provider).checked = true;
  $('cap').value = String(cfg.daily_cap != null ? cfg.daily_cap : 30);
  $('fallback').setAttribute('aria-checked', String(!(local.prefs && local.prefs.fallback === false)));
}

function setModelOptions(sel, placeholder, ids, selected) {
  sel.textContent = '';
  const add = (value, label) => { const o = document.createElement('option'); o.value = value; o.textContent = label; sel.appendChild(o); };
  add('', placeholder);
  for (const id of ids) add(id, id);
  sel.value = ids.includes(selected) ? selected : '';
}

async function loadModels() {
  const provider = currentProvider();
  const token = ++modelsToken;
  const sel = $('model');
  const err = $('ai-error');
  setText($('model-label'), `Model (from ${PROVIDER_NAMES[provider]}'s model list)`);
  sel.disabled = true;
  setModelOptions(sel, 'Loading models…', [], '');
  show(err, false);
  show($('key-line'), false);
  const res = await send({ type: 'MODELS', provider });
  if (token !== modelsToken) return; // the provider changed while this was loading

  if (res && res.models) {
    const saved = ((local.config || {}).models || {})[provider] || '';
    setModelOptions(sel, '— pick a model —', res.models, saved);
    sel.disabled = false;
    setText($('key-line'), `Key: saved in Keychain (job-autofill-${provider})`);
    show($('key-line'), true);
    return;
  }
  if (res && res.offline) {
    setModelOptions(sel, 'Helper offline', [], '');
    setText(err, 'Helper offline — models unavailable.');
    err.className = 'warnline';
    show(err, true);
    return;
  }
  const text = (res && res.error) || 'Models unavailable';
  const m = /^(.*run:)\s*(.+)$/.exec(text);
  err.className = 'errline';
  err.textContent = '';
  if (m) {
    err.append(`${m[1]} `);
    const code = document.createElement('span');
    code.className = 'mono';
    code.textContent = m[2];
    err.append(code);
    setModelOptions(sel, 'Add a key to load models', [], '');
  } else {
    err.textContent = text;
    setModelOptions(sel, 'Models unavailable', [], '');
  }
  show(err, true);
}

async function onProviderChange() {
  $('model').disabled = true;
  const msg = $('ai-msg');
  msg.className = 'msg';
  setText(msg, '');
  const res = await send({ type: 'SAVE_CONFIG', patch: { provider: currentProvider() } });
  if (res && res.error) { msg.classList.add('err'); setText(msg, res.error); }
  await refresh();
  await loadModels();
}

async function onSaveAi() {
  const msg = $('ai-msg');
  msg.className = 'msg';
  const capText = $('cap').value.trim();
  if (!/^\d+$/.test(capText)) { msg.classList.add('err'); setText(msg, 'AI calls per day must be a whole number.'); return; }
  const provider = currentProvider();
  const patch = { provider, daily_cap: Number(capText) };
  if (!$('model').disabled) patch.models = { [provider]: $('model').value };
  const res = await send({ type: 'SAVE_CONFIG', patch, fallback: $('fallback').getAttribute('aria-checked') === 'true' });
  if (res && res.ok) { msg.classList.add('ok'); setText(msg, 'Saved'); await refresh(); }
  else { msg.classList.add('err'); setText(msg, (res && res.error) || 'Not saved'); }
}

// ---- tabs, switches, pairing -------------------------------------------------------------
const PANELS = ['run', 'profile', 'ai'];

function selectPanel(name, focus) {
  for (const p of PANELS) {
    const t = $('tab-' + p);
    const on = p === name;
    t.setAttribute('aria-selected', String(on));
    t.tabIndex = on ? 0 : -1;
    show($('panel-' + p), on);
    if (on && focus) t.focus();
  }
  if (name === 'profile') renderProfile();
  if (name === 'ai') { renderAi(); loadModels(); }
}

function wireTabs() {
  for (const p of PANELS) {
    $('tab-' + p).addEventListener('click', () => selectPanel(p, false));
    $('tab-' + p).addEventListener('keydown', (e) => {
      const i = PANELS.indexOf(p);
      let n = null;
      if (e.key === 'ArrowRight') n = (i + 1) % PANELS.length;
      else if (e.key === 'ArrowLeft') n = (i + PANELS.length - 1) % PANELS.length;
      else if (e.key === 'Home') n = 0;
      else if (e.key === 'End') n = PANELS.length - 1;
      if (n !== null) { e.preventDefault(); selectPanel(PANELS[n], true); }
    });
  }
}

function toggle(el) {
  if (el.getAttribute('aria-disabled') === 'true') return;
  el.setAttribute('aria-checked', String(el.getAttribute('aria-checked') !== 'true'));
}

async function onPair() {
  const msg = $('pair-msg');
  setText(msg, '');
  const res = await send({ type: 'PAIR', token: $('token').value });
  if (res && res.ok) {
    $('token').value = '';
    syncStatus = 'ok';
    await refresh();
    renderAll();
  } else {
    setText(msg, (res && res.error) || 'Pairing failed');
  }
}

function renderAll() {
  renderHeader();
  renderViews();
  renderRun();
  if (!$('panel-profile').hidden) renderProfile();
}

async function init() {
  wireTabs();
  $('pair').addEventListener('click', onPair);
  $('token').addEventListener('keydown', (e) => { if (e.key === 'Enter') onPair(); });
  $('run').addEventListener('click', onRun);
  $('submit').addEventListener('click', () => { if (!activeRun()) { submitOn = !submitOn; renderRun(); } });
  $('fallback').addEventListener('click', () => toggle($('fallback')));
  $('profile-save').addEventListener('click', onSaveProfile);
  $('ai-save').addEventListener('click', onSaveAi);
  $('resume-change').addEventListener('click', () => {
    const open = $('resume-edit').hidden;
    show($('resume-edit'), open);
    $('resume-change').setAttribute('aria-expanded', String(open));
    if (open) $('resume-path').focus();
  });
  $('resume-set').addEventListener('click', onSetResume);
  for (const p of ['anthropic', 'openai']) $('prov-' + p).addEventListener('change', onProviderChange);

  tab = await resolveTab();
  await refresh();
  renderAll();
  renderProfile();

  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === 'session' && changes.runs) {
      runs = changes.runs.newValue || {};
      renderRun();
    } else if (area === 'local' && (changes.syncedAt || changes.token)) {
      refresh().then(renderAll);
    }
  });

  if (local.token) {
    const res = await send({ type: 'SYNC' });
    syncStatus = res && res.status === 'ok' ? 'ok' : (res && res.status === 'rejected' ? 'rejected' : 'offline');
    await refresh();
    renderAll();
    renderProfile();
  }
}

init();
