// Content-script entry. Classic script; shares globalThis.AF with the other content files
// (load order: util, scorer, matcher, drafts, adapters, fill, hud, main).
//
// Handles START from the background in every frame, fills the frame, highlights, reports
// REPORT {runId, status, step, counts} and, in the top frame only, shows the page panel.
// The background re-injects these files into tabs that were open before install, so loading
// twice must be harmless: the guard below makes this file a no-op the second time.
(function (root) {
  'use strict';
  if (root.__AF_LOADED) return;
  root.__AF_LOADED = true;

  const AF = root.AF;
  const isTop = root.top === root;
  let currentRun = null;
  let lastItems = [];
  let lastStep = 1;
  const stepCounts = new Map();
  let signIn = false;
  AF.pageSafety = () => ({
    captcha: AF.captcha(),
    yellow: lastItems.filter(i => i.level === 'yellow' && !['Required field still needs input', "Couldn't set this field"].includes(i.reason)).length,
    aiDrafts: lastItems.filter(i => i.ai).length,
    required: lastItems.filter(i => i.reason === 'Required field still needs input').length,
    readback: lastItems.filter(i => i.reason === "Couldn't set this field" || (i.filled !== false && i.read && !i.read(i.el))).length,
    button: AF.safeButton(AF.adapterFor(location.hostname))?.kind || '',
  });

  async function finish(msg, status, reason = '', code = '') {
    AF.wizard.stop();
    await chrome.runtime.sendMessage({ type: 'LOG_RUN', runId: msg.runId, status, reason, code });
  }

  async function settle(msg) {
    if (!isTop || currentRun !== msg.runId) return;
    let state;
    do {
      state = await chrome.runtime.sendMessage({ type: 'PAGE_STATE', runId: msg.runId });
      if (!state?.ready) await AF.util.sleep(100);
    } while (currentRun === msg.runId && !state?.ready);
    if (currentRun !== msg.runId) return;
    if (signIn) return finish(msg, 'stopped', "Sign in first — AutoFill doesn't sign in or create accounts", 'signin');
    if (!msg.submit) return finish(msg, 'filled');
    const check = AF.safetyCheck(state.safety);
    if (!check.ok) return finish(msg, 'stopped', check.reason, check.code);
    const action = await chrome.runtime.sendMessage({ type: 'SAFE_ACTION', runId: msg.runId });
    if (action?.error) return finish(msg, 'stopped', action.error, action.code || 'button');
    if (action.kind === 'submit') {
      AF.wizard.stop();
      const end = Date.now() + 15000;
      while (currentRun === msg.runId && Date.now() < end) {
        if (AF.confirmed(AF.adapterFor(location.hostname))) return finish(msg, 'submitted_confirmed');
        await AF.util.sleep(100);
      }
      if (currentRun === msg.runId) return finish(msg, 'submitted_unconfirmed');
    }
  }

  async function loadResume() {
    const { resume, resumeError } = await chrome.storage.local.get(['resume', 'resumeError']);
    return { resume: resume && resume.b64 ? resume : null, resumeError: resumeError || '' };
  }

  function summarize(items, fields) {
    const green = items.filter((i) => i.level === 'green').length;
    const yellow = items.filter((i) => i.level === 'yellow').length;
    const filled = items.filter((i) => i.filled !== false).length;
    return { green, yellow, filled, fields };
  }

  function questionText(item) {
    return AF.util.groupLabel && item.kind === 'radio'
      ? AF.util.groupLabel(item.el)
      : AF.util.labelText(item.el);
  }

  function panelFor(runId, counts, items) {
    const review = items
      .filter((i) => i.level === 'yellow')
      .map((i) => ({ label: questionText(i), reason: i.reason }));
    let message = '';
    if (signIn) return { runId, counts, review: [], message: "Sign in first — AutoFill doesn't sign in or create accounts", tone: 'rv' };
    let tone = 'done';
    if (counts.yellow) {
      message = counts.yellow === 1 ? 'Review the yellow field, then submit yourself.' : 'Review the yellow fields, then submit yourself.';
      tone = 'rv';
    } else if (counts.filled) {
      message = 'Nothing to review. Check the form, then submit yourself.';
    } else {
      message = 'No form fields found on this page.';
      tone = 'rv';
    }
    return { runId, counts, review, message, tone };
  }

  async function fillStep(msg, step = 1) {
    const { resume, resumeError } = await loadResume();
    const { config } = await chrome.storage.local.get('config');
    const adapter = AF.adapterFor(root.location.hostname);
    const result = await AF.fillPage(root.document, msg.profile || {}, resume, {
      adapter, resumeError, fallback: msg.fallback,
      aiEnabled: !!config?.models?.[config.provider],
    });
    if (currentRun !== msg.runId) return;
    signIn = !!result.signIn;
    for (const it of result.items) AF.highlight(it.el, it.level, it.reason);
    lastItems = result.items;
    lastStep = step;
    stepCounts.set(step, { ...summarize(result.items, result.fields), ai_drafts: result.aiDrafts || 0, ai_calls: result.aiCalls || 0 });
    const counts = { green: 0, yellow: 0, filled: 0, fields: 0, ai_drafts: 0, ai_calls: 0 };
    for (const snapshot of stepCounts.values()) {
      for (const key of Object.keys(snapshot)) counts[key] += snapshot[key];
    }
    await chrome.runtime.sendMessage({
      type: 'REPORT',
      summary: { runId: msg.runId, status: msg.submit ? 'running' : 'filled', step, counts, ats: adapter.name },
    }).catch(() => {});
  }

  async function run(msg) {
    AF.wizard.stop();
    currentRun = msg.runId;
    stepCounts.clear();
    lastItems = [];
    lastStep = 1;
    signIn = false;
    AF.clearHighlights();
    if (isTop) AF.hud.render({ runId: msg.runId, message: 'Filling\u2026', tone: 'rv' });
    await fillStep(msg);
    if (currentRun === msg.runId && !signIn) AF.wizard.start(msg);
    await settle(msg);
  }

  AF.wizard.onStep(({ runCtx, step }) => {
    fillStep(runCtx, step).then(() => settle(runCtx)).catch(() => {});
  });

  // Session updates include every frame. The top panel and popup consume the same totals.
  if (isTop) chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== 'session' || !changes.runs || !currentRun) return;
    const state = Object.values(changes.runs.newValue || {}).find((r) => r.runId === currentRun);
    if (!state) return;
    const summary = panelFor(currentRun, state.counts, lastItems);
    const step = Math.max(lastStep, state.step || 1);
    if (state.status === 'stopped') {
      summary.message = state.reason === 'Already submitted from this tab' ? state.reason : `Stopped: ${state.reason}`;
      summary.tone = 'stop';
    } else if (state.status === 'submitted_confirmed' || state.status === 'submitted_unconfirmed') {
      summary.message = state.status === 'submitted_confirmed' ? 'Submitted · confirmed' : 'Submitted · not confirmed — check the page before trying again';
      summary.tone = 'done';
    }
    if (step > 1) summary.title = `AutoFill · ${state.counts.filled} filled · Step ${step}`;
    AF.hud.render(summary);
  });

  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg?.type === 'SAFE_CLICK' && sender.id === chrome.runtime.id && msg.runId === currentRun) {
      const button = AF.safeButton(AF.adapterFor(location.hostname));
      if (button) AF.util.click(button.el);
      sendResponse({ ok: !!button });
      return false;
    }
    if (!msg || msg.type !== 'START' || sender.id !== chrome.runtime.id) return false;
    run(msg).catch((e) => {
      chrome.runtime.sendMessage({
        type: 'REPORT',
        summary: { runId: msg.runId, status: 'error', reason: String((e && e.message) || e) },
      }).catch(() => {});
    });
    sendResponse({ ok: true });
    return false;
  });

  if (isTop) chrome.runtime.sendMessage({ type: 'RUN_STATE' }).then(async state => {
    if (!state?.pendingSubmit) return;
    currentRun = state.runId;
    lastStep = state.step || 1;
    const sourceAdapter = AF.adapterFor(state.sourceHostname);
    if (AF.confirmed(sourceAdapter)) await finish(state, 'submitted_confirmed');
  }).catch(() => {});
})(globalThis);
