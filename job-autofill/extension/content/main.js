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
    const adapter = AF.adapterFor(root.location.hostname);
    const result = await AF.fillPage(root.document, msg.profile || {}, resume, { adapter, resumeError, fallback: msg.fallback });
    if (currentRun !== msg.runId) return;
    for (const it of result.items) AF.highlight(it.el, it.level, it.reason);
    lastItems = result.items;
    lastStep = step;
    stepCounts.set(step, summarize(result.items, result.fields));
    const counts = { green: 0, yellow: 0, filled: 0, fields: 0, ai_drafts: 0, ai_calls: 0 };
    for (const snapshot of stepCounts.values()) {
      for (const key of Object.keys(snapshot)) counts[key] += snapshot[key];
    }
    await chrome.runtime.sendMessage({
      type: 'REPORT',
      summary: { runId: msg.runId, status: 'filled', step, counts },
    }).catch(() => {});
  }

  async function run(msg) {
    AF.wizard.stop();
    currentRun = msg.runId;
    stepCounts.clear();
    lastItems = [];
    lastStep = 1;
    AF.clearHighlights();
    if (isTop) AF.hud.render({ runId: msg.runId, message: 'Filling\u2026', tone: 'rv' });
    await fillStep(msg);
    if (currentRun === msg.runId) AF.wizard.start(msg);
  }

  AF.wizard.onStep(({ runCtx, step }) => {
    fillStep(runCtx, step).catch(() => {});
  });

  // Session updates include every frame. The top panel and popup consume the same totals.
  if (isTop) chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== 'session' || !changes.runs || !currentRun) return;
    const state = Object.values(changes.runs.newValue || {}).find((r) => r.runId === currentRun);
    if (!state) return;
    const summary = panelFor(currentRun, state.counts, lastItems);
    const step = Math.max(lastStep, state.step || 1);
    if (step > 1) summary.title = `AutoFill · ${state.counts.filled} filled · Step ${step}`;
    AF.hud.render(summary);
  });

  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
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
})(globalThis);
