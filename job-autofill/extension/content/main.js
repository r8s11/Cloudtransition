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
  let cancellation = null;
  let signIn = false;
  let partial = null; // the fill in progress: {runId, step, items}
  AF.pageSafety = () => ({
    captcha: AF.captcha(),
    yellow: lastItems.filter(i => i.level === 'yellow' && !['Required field still needs input', "Couldn't set this field"].includes(i.reason)).length,
    aiDrafts: lastItems.filter(i => i.ai).length,
    required: AF.requiredEmptyCount(root.document),
    readback: lastItems.filter(i => i.reason === "Couldn't set this field" || (i.filled !== false && i.read && !i.read(i.el))).length,
    button: AF.safeButton(AF.adapterFor(location.hostname))?.kind || '',
  });

  async function finish(msg, status, reason = '', code = '') {
    if (currentRun !== msg.runId) return;
    AF.wizard.stop();
    cancellation?.abort();
    // shortcut: partial fills report 0 fields and 0 AI counts, upgrade if the log needs them.
    if (partial?.runId === msg.runId) await report(msg, partial.step, { items: partial.items, fields: 0 });
    partial = null;
    await chrome.runtime.sendMessage({ type: 'LOG_RUN', runId: msg.runId, status, reason, code });
  }

  async function settle(msg) {
    if (!isTop || currentRun !== msg.runId || cancellation?.signal.aborted) return;
    let state;
    do {
      state = await chrome.runtime.sendMessage({ type: 'PAGE_STATE', runId: msg.runId });
      if (!state?.ready) await AF.util.sleep(100);
    } while (currentRun === msg.runId && !cancellation?.signal.aborted && !state?.ready);
    if (currentRun !== msg.runId || cancellation?.signal.aborted) return;
    if (signIn) return finish(msg, 'stopped', "Sign in first — AutoFill doesn't sign in or create accounts", 'signin');
    if (!msg.submit) {
      if (state.action?.kind !== 'next') return finish(msg, 'filled');
      if (lastStep >= 10) return finish(msg, 'stopped', '10-step limit', 'limit');
      return;
    }
    const check = AF.safetyCheck(state.safety);
    if (!check.ok) return finish(msg, 'stopped', check.reason, check.code);
    if (lastStep >= 10 && state.action?.kind === 'next') return finish(msg, 'stopped', '10-step limit', 'limit');
    if (state.action?.kind === 'next') AF.wizard.advancing();
    const action = await chrome.runtime.sendMessage({ type: 'SAFE_ACTION', runId: msg.runId });
    if (action?.error) return finish(msg, 'stopped', action.error, action.code || 'button');
    if (action.kind === 'submit') return waitForConfirmation(msg, AF.adapterFor(location.hostname), action.deadline);
  }

  async function waitForConfirmation(msg, adapter, deadline) {
    AF.wizard.stop();
    while (currentRun === msg.runId && Date.now() < deadline) {
      if (AF.confirmed(adapter)) return finish(msg, 'submitted_confirmed');
      await AF.util.sleep(100);
    }
    if (currentRun === msg.runId) return finish(msg, 'submitted_unconfirmed');
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
    if (cancellation?.signal.aborted || currentRun !== msg.runId) return;
    const adapter = AF.adapterFor(root.location.hostname);
    partial = { runId: msg.runId, step, items: [] };
    const result = await AF.fillPage(root.document, msg.profile || {}, resume, {
      adapter, resumeError, fallback: msg.fallback, signal: cancellation.signal,
      aiEnabled: !!config?.models?.[config.provider], items: partial.items, runId: msg.runId,
    });
    if (currentRun !== msg.runId || cancellation.signal.aborted) return;
    partial = null;
    signIn = !!result.signIn;
    for (const it of result.items) AF.highlight(it.el, it.level, it.reason);
    lastItems = result.items;
    lastStep = step;
    await report(msg, step, result);
  }

  async function report(msg, step, result) {
    stepCounts.set(step, { ...summarize(result.items, result.fields), ai_drafts: result.aiDrafts || 0, ai_calls: result.aiCalls || 0 });
    const counts = { green: 0, yellow: 0, filled: 0, fields: 0, ai_drafts: 0, ai_calls: 0 };
    for (const snapshot of stepCounts.values()) {
      for (const key of Object.keys(snapshot)) counts[key] += snapshot[key];
    }
    await chrome.runtime.sendMessage({
      type: 'REPORT',
      summary: { runId: msg.runId, status: msg.submit ? 'running' : 'filled', step, counts, ats: AF.adapterFor(root.location.hostname).name, fingerprint: AF.wizard.fingerprint() },
    }).catch(() => {});
  }

  async function run(msg) {
    AF.wizard.stop();
    cancellation?.abort();
    cancellation = new AbortController();
    msg.onStop = (reason, code) => finish(msg, 'stopped', reason, code);
    currentRun = msg.runId;
    stepCounts.clear();
    lastItems = [];
    lastStep = 1;
    signIn = false;
    AF.clearHighlights();
    if (isTop) AF.hud.render({ runId: msg.runId, message: 'Filling\u2026', tone: 'rv', canStop: true }, {
      onStop: () => finish(msg, 'stopped'),
    });
    await fillStep(msg);
    if (currentRun === msg.runId && !signIn && !cancellation.signal.aborted) AF.wizard.start(msg);
    await settle(msg);
  }

  AF.wizard.onStep(({ runCtx, step }) => {
    if (cancellation?.signal.aborted) return;
    fillStep(runCtx, step).then(() => settle(runCtx)).catch(() => {});
  });

  // Session updates include every frame. The top panel and popup consume the same totals.
  if (isTop) chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== 'session' || !changes.runs || !currentRun) return;
    const state = Object.values(changes.runs.newValue || {}).find((r) => r.runId === currentRun);
    if (!state) return;
    const summary = panelFor(currentRun, state.counts, lastItems);
    summary.canStop = !state.logged;
    if (state.logged) {
      AF.wizard.stop();
      cancellation?.abort();
    }
    const step = Math.max(lastStep, state.step || 1);
    if (state.status === 'stopped') {
      summary.message = state.reason === 'Already submitted from this tab' ? state.reason : state.reason ? `Stopped: ${state.reason}` : 'Stopped';
      summary.tone = 'stop';
    } else if (state.status === 'submitted_confirmed' || state.status === 'submitted_unconfirmed') {
      summary.message = state.status === 'submitted_confirmed' ? 'Submitted · confirmed' : 'Submitted · not confirmed — check the page before trying again';
      summary.tone = 'done';
    }
    if (step > 1) summary.title = `AutoFill · ${state.counts.filled} filled · Step ${step}`;
    AF.hud.render(summary);
  });

  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg?.type === 'STOP_RUN' && sender.id === chrome.runtime.id && msg.runId === currentRun) {
      cancellation?.abort();
      AF.wizard.stop();
      sendResponse({ ok: true });
      return false;
    }
    if (msg?.type === 'SAFE_CLICK' && sender.id === chrome.runtime.id && msg.runId === currentRun) {
      // Live recheck at click time: the page may have changed since the background's snapshot.
      const button = AF.safeButton(AF.adapterFor(location.hostname));
      const check = AF.safetyCheck({ ...AF.pageSafety(), button: !!button });
      const ok = check.ok && button.kind === msg.kind && !cancellation?.signal.aborted;
      if (ok) AF.util.click(button.el);
      sendResponse(ok ? { ok } : check.ok ? { error: 'No safe Next or Submit button found', code: 'button' } : { error: check.reason, code: check.code });
      return false;
    }
    if (!msg || msg.type !== 'START' || sender.id !== chrome.runtime.id) return false;
    run(msg).catch((e) => {
      if (cancellation?.signal.aborted) return;
      chrome.runtime.sendMessage({
        type: 'REPORT',
        summary: { runId: msg.runId, status: 'error', reason: String((e && e.message) || e) },
      }).catch(() => {});
    });
    sendResponse({ ok: true });
    return false;
  });

  if (isTop) chrome.runtime.sendMessage({ type: 'DOCUMENT_READY' }).then(async state => {
    if (!state?.pendingSubmit) return;
    currentRun = state.runId;
    lastStep = state.step || 1;
    const sourceAdapter = AF.adapterFor(state.sourceHostname);
    await waitForConfirmation(state, sourceAdapter, state.submitDeadline);
  }).catch(() => {});
})(globalThis);
