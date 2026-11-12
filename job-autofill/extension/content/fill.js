// Fill engine: finds the controls on a page, fills them from the profile, reads every value
// back after a settle delay, and returns what happened. Classic script; attaches to globalThis.AF.
//
//   AF.fillPage(root, profile, resume, opts) -> Promise<{items, aiQueue, fields}>
//     items: [{el, key, level: 'green'|'yellow', reason, filled}]   filled:false = nothing was put in
//     fields: number of fillable controls found (prefilled ones included)
//     resume: {name, type, b64} | null
//     opts: {adapter?, resumeError?}
(function (root) {
  'use strict';
  const AF = (root.AF = root.AF || {});
  if (AF.fillPage) return; // Re-injection must preserve read-back history.
  const U = AF.util;

  const SETTLE_MS = 150;
  const TEXT_TYPES = new Set(['text', 'email', 'tel', 'url', 'number', '']);
  const RESUME_RE = /\b(resume|r\u00e9sum\u00e9|cv|curriculum vitae)\b/i;
  const NEVER_RE = /\b(cover|letter|photo|picture|transcript|portfolio|writing sample|certificate|reference)\b/i;

  const R_PROFILE = 'From profile';
  const R_QUESTION = 'Question-style label \u2014 check this answer';
  const R_CLOSE = 'Close match \u2014 check this option';
  const R_STUCK = "Couldn't set this field";
  const R_REQUIRED = 'Required field still needs input';
  const R_UNLABELED = "Unlabeled upload \u2014 check it's the resume box";
  const R_NO_RESUME = 'Resume file not found \u2014 pick it in Profile';

  // Controls this run filled, so a second run on the same page counts them instead of
  // mistaking them for fields the site prefilled.
  const filledBefore = new WeakMap();

  function valueFor(key, p) {
    if (!key || !p) return '';
    if (key === 'location') return [p.city, p.state].filter((v) => v && String(v).trim()).join(', ');
    const v = p[key];
    return typeof v === 'string' ? v.trim() : '';
  }

  function isRequired(el) {
    return el.required || el.getAttribute('aria-required') === 'true';
  }

  function isPlaceholderOption(opt) {
    return !opt || opt.disabled || opt.value === '' || AF.isPlaceholder(opt.textContent);
  }

  function selectHasValue(el) {
    return el.selectedIndex >= 0 && !isPlaceholderOption(el.options[el.selectedIndex]);
  }

  function ctxOf(el) {
    return {
      label: U.labelText(el),
      name: el.getAttribute('name') || '',
      id: el.id || '',
      placeholder: el.getAttribute('placeholder') || '',
      autocomplete: el.getAttribute('autocomplete') || '',
      automationId: el.getAttribute('data-automation-id') || '',
    };
  }

  function radiosOf(radio) {
    if (!radio.name) return [radio];
    const scope = radio.form || radio.getRootNode();
    return Array.from(scope.querySelectorAll('input[type=radio]')).filter((r) => r.name === radio.name);
  }

  function optionScore(label, value, target) {
    return AF.scoreOption(label, value, target);
  }

  const tick = () => new Promise((r) => setTimeout(r, 0));

  async function fillPage(scope, profile, resume, opts) {
    opts = opts || {};
    const adapter = opts.adapter || AF.adapterFor(root.location.hostname);
    if (adapter.isSignIn(scope)) return { items: [], aiQueue: [], fields: 0, signIn: true };
    const signInForms = new Set(U.deepQueryAll(scope, 'form').filter((form) => adapter.isSignIn(form)));
    const inSignInForm = (el) => signInForms.has(el.form || el.closest('form'));
    const claims = new Map();
    for (const { el, key } of adapter.fields(scope)) claims.set(el, key);
    const widgets = (adapter.widgets ? adapter.widgets(scope)
      : U.deepQueryAll(scope, '[role=combobox], [aria-haspopup=listbox]')
        .filter((el) => el.tagName !== 'SELECT')
        .map((el) => ({ el, key: claims.get(el) || AF.matchField(ctxOf(el)).key, kind: 'combo' })))
      .filter(({ el }) => !inSignInForm(el));
    const widgetElements = new Set(widgets.map(({ el }) => el));
    const dropSlots = widgets.filter(({ kind }) => kind === 'drop');

    const all = U.deepQueryAll(scope, U.CONTROLS).filter((el) => !inSignInForm(el));
    const items = opts.items || [];
    const pending = []; // entries that need a read-back
    const seenGroups = new Set();
    const handled = new Set(); // controls that already have an item or were left alone
    const fileInputs = [];
    let fields = 0;

    const add = (entry) => { items.push(entry); handled.add(entry.el); return entry; };

    let n = 0;
    for (const el of all) {
      if ((n += 1) % 25 === 0) await tick();
      opts.signal?.throwIfAborted();
      // Editable comboboxes must select an option, not merely accept a text value.
      if (widgetElements.has(el)) continue;
      const tag = el.tagName;
      const type = tag === 'INPUT' ? el.type : tag === 'SELECT' ? 'select' : 'textarea';
      if (el.disabled || el.readOnly) continue;

      if (type === 'file') {
        fileInputs.push(el);
        continue;
      }
      if (!U.isVisible(el)) continue;

      if (type === 'radio') {
        const group = radiosOf(el);
        const gid = group[0];
        if (seenGroups.has(gid)) continue;
        seenGroups.add(gid);
        fields += 1;
        fillRadioGroup(group, claims, profile, pending, add, handled);
        continue;
      }
      if (type === 'checkbox') { fields += 1; continue; }
      if (tag === 'INPUT' && !TEXT_TYPES.has(type)) continue;
      fields += 1;

      if (reuse(el, add)) continue;

      if (type === 'select') {
        if (selectHasValue(el)) { handled.add(el); continue; }
        fillSelect(el, claims, profile, pending, add);
        continue;
      }
      if (el.value.trim() !== '') { handled.add(el); continue; }
      fillText(el, claims, profile, pending, add);
    }

    fillFiles(fileInputs, claims, resume, opts, pending, add, handled);
    fields += fileInputs.filter((f) => !f.disabled).length;
    let widgetCount = 0;
    for (const widget of widgets) {
      if (++widgetCount % 25 === 0) await tick();
      opts.signal?.throwIfAborted();
      if (!U.isVisible(widget.el) || widget.el.disabled || widget.el.getAttribute('aria-disabled') === 'true') continue;
      fields += 1;
      if (!reuse(widget.el, add)) await fillWidget(widget, profile, resume, opts, pending, add, dropSlots.length);
    }

    await U.sleep(SETTLE_MS);
    opts.signal?.throwIfAborted();
    for (const p of pending) await verify(p, opts);

    const aiQueue = all.filter((el) => {
      if (handled.has(el) || widgetElements.has(el) || !U.isVisible(el) || el.disabled || el.readOnly) return false;
      const form = el.form || el.closest('form');
      const hasValue = el.tagName === 'SELECT' ? selectHasValue(el) : !!el.value.trim();
      if (!form || hasValue || claims.has(el) || AF.matchField(ctxOf(el)).key) return false;
      if (!['TEXTAREA', 'SELECT'].includes(el.tagName) && !(el.tagName === 'INPUT' && ['text', 'number'].includes(el.type))) return false;
      const excluded = /\b(search|sign.?in|log.?in|password|captcha|promo|coupon|newsletter|subscribe|hispanic|latino|race|ethnicity|gender|sex|veteran|disabilit(y|ies)|demographic|self.?identify)\b/i;
      const context = `${U.labelText(el)} ${el.name} ${el.id}`;
      return !!U.labelText(el) && !excluded.test(formContext) && !excluded.test(context);
    });
    requiredPass(all, items, add);
    let aiCalls = 0;
    let aiDrafts = 0;
    if (opts.aiEnabled) {
      for (const el of aiQueue) {
        const fieldType = el.tagName === 'SELECT' ? 'select' : el.type === 'number' ? 'number' : 'text';
        const options = el.tagName === 'SELECT' ? Array.from(el.options).filter((o) => !isPlaceholderOption(o)).map((o) => U.clean(o.textContent)) : undefined;
        const req = {
          question: U.labelText(el), field_type: fieldType, max_length: Math.max(0, el.maxLength || 0),
          page_title: document.title,
          company: U.clean(Array.from(document.querySelectorAll('.company-name, [data-company]')).find(U.isVisible)?.textContent || ''),
          job_heading: U.clean(Array.from(document.querySelectorAll('h1')).find(U.isVisible)?.textContent || ''),
        };
        if (options) req.options = options;
        let reply;
        try { reply = await chrome.runtime.sendMessage({ type: 'DRAFT', req }); }
        catch (_) { reply = { error: 'Helper offline — AI drafts unavailable' }; }
        opts.signal?.throwIfAborted();
        let entry = items.find((item) => item.el === el);
        if (!entry) entry = add({ el, key: null, kind: 'text' });
        Object.assign(entry, { filled: false, level: 'yellow', reason: 'AI draft — review before submitting', ai: true });
        if (reply?.error) {
          entry.reason = String(reply.error).replace(/^AutoFill: /, '');
          if (/^AI error:/.test(entry.reason)) aiCalls += 1;
          continue;
        }
        if (reply?.cached === false) aiCalls += 1;
        const value = AF.postProcess(reply?.text, { fieldType, maxLength: req.max_length, options });
        if (value == null) { entry.reason = 'AI error: unreadable reply'; continue; }
        const actual = options ? Array.from(el.options).find((o) => U.clean(o.textContent) === value)?.value : value;
        U.setNative(el, actual);
        Object.assign(entry, { value: actual, read: (e) => e.value === actual });
        await U.sleep(SETTLE_MS);
        await verify(entry, opts);
        if (entry.reason !== R_STUCK) {
          entry.filled = true;
          aiDrafts += 1;
        }
      }
    }
    return { items, aiQueue, fields, aiCalls, aiDrafts };
  }

  // Portal lists are resolved after opening, never from hidden stale options.
  async function fillWidget({ el, key, kind }, profile, resume, opts, pending, add, dropCount) {
    if (kind === 'drop') {
      const label = U.labelText(el);
      const hint = label || `${el.getAttribute('name') || ''} ${el.id} ${U.clean(el.textContent)}`;
      if (NEVER_RE.test(hint)) return;
      const level = RESUME_RE.test(hint) ? 'green' : dropCount === 1 && !label ? 'yellow' : null;
      if (!level) return;
      if (!resume || !resume.b64) {
        add({ el, key, kind, filled: false, level: 'yellow', reason: opts.resumeError || R_NO_RESUME });
        return;
      }
      if (el.textContent.includes(resume.name)) return;
      const dt = new root.DataTransfer();
      dt.items.add(U.fileFrom(resume));
      for (const type of ['dragenter', 'dragover', 'drop']) {
        el.dispatchEvent(new root.DragEvent(type, { bubbles: true, cancelable: true, dataTransfer: dt }));
      }
      pending.push(add({
        el, key, kind, filled: true, level, reason: level === 'green' ? R_PROFILE : R_UNLABELED,
        read: (e) => e.textContent.includes(resume.name)
          || U.deepQueryAll(e, 'input[type=file]').some((f) => f.files[0]?.name === resume.name),
      }));
      return;
    }
    const value = valueFor(key, profile);
    const shown = () => U.clean(el.value || el.textContent);
    if (!value || (shown() && !AF.isPlaceholder(shown()))) return;
    U.click(el);
    let options = [];
    for (let tries = 0; tries < 10; tries += 1) {
      const ids = (el.getAttribute('aria-controls') || el.getAttribute('aria-owns') || '').split(/\s+/);
      const containers = ids.map((id) => el.getRootNode().getElementById(id) || el.ownerDocument.getElementById(id)).filter(Boolean);
      options = (containers.length ? containers.flatMap((c) => U.deepQueryAll(c, '[role=option], [data-automation-id=promptOption]'))
        : U.deepQueryAll(el.ownerDocument, '[role=option], [data-automation-id=promptOption]')).filter(U.isVisible);
      if (options.length) break;
      await U.sleep(50);
      opts.signal?.throwIfAborted();
    }
    const hit = bestOption(options.map((option) => ({ option, label: U.clean(option.textContent), value: option.getAttribute('data-value') || '' })), value);
    if (hit) U.click(hit.option.option);
    if (el.getAttribute('aria-expanded') === 'true') {
      el.dispatchEvent(new root.KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', bubbles: true }));
      if (el.getAttribute('aria-expanded') === 'true') U.click(el);
    }
    if (!hit) return;
    const entry = {
      el, key, kind, value, filled: true, level: hit.score >= 85 ? 'green' : 'yellow',
      reason: hit.score >= 85 ? R_PROFILE : R_CLOSE,
      read: () => {
        const score = AF.scoreOption(shown(), '', value);
        if (score < 70 || el.getAttribute('aria-expanded') === 'true') return false;
        entry.level = score >= 85 ? 'green' : 'yellow';
        entry.reason = score >= 85 ? R_PROFILE : R_CLOSE;
        return true;
      },
    };
    pending.push(add(entry));
  }

  function fillText(el, claims, profile, pending, add) {
    const claimed = claims.get(el);
    let key = claimed;
    let questionStyle = false;
    if (!key) {
      const m = AF.matchField(ctxOf(el));
      key = m.key;
      questionStyle = m.questionStyle;
    }
    if (!key || key === 'resume') return;
    const value = valueFor(key, profile);
    if (!value) return;
    U.setNative(el, value);
    const yellow = !claimed && questionStyle;
    pending.push(add({
      el, key, kind: 'text', value, filled: true,
      level: yellow ? 'yellow' : 'green', reason: yellow ? R_QUESTION : R_PROFILE,
      read: (e) => e.value === value,
    }));
  }

  function bestOption(options, target) {
    let best = null;
    let top = 0;
    for (const o of options) {
      const s = optionScore(o.label, o.value, target);
      if (s > top) { top = s; best = o; }
    }
    return top >= 70 ? { option: best, score: top } : null;
  }

  function fillSelect(el, claims, profile, pending, add) {
    const claimed = claims.get(el);
    const key = claimed || AF.matchField(ctxOf(el)).key;
    const value = valueFor(key, profile);
    if (!key || !value) return;
    const options = Array.from(el.options).map((opt, index) => ({ opt, index, label: opt.textContent, value: opt.value }));
    const hit = bestOption(options.filter((o) => !isPlaceholderOption(o.opt)), value);
    if (!hit) return;
    const { opt, index } = hit.option;
    U.setNative(el, opt.value);
    if (el.selectedIndex !== index) { el.selectedIndex = index; el.dispatchEvent(new Event('change', { bubbles: true })); }
    const entry = {
      el, key, kind: 'select', value, filled: true,
      level: hit.score >= 85 ? 'green' : 'yellow', reason: hit.score >= 85 ? R_PROFILE : R_CLOSE,
      read: (e) => {
        const selected = e.options[e.selectedIndex];
        if (isPlaceholderOption(selected)) return false;
        const score = optionScore(selected.textContent, selected.value, value);
        if (score < 70) return false;
        entry.level = score >= 85 ? 'green' : 'yellow';
        entry.reason = score >= 85 ? R_PROFILE : R_CLOSE;
        return true;
      },
    };
    pending.push(add(entry));
  }

  // True when this run's earlier pass filled the control and its value is still there.
  function reuse(el, add) {
    const before = filledBefore.get(el);
    if (!before || !before.read(el)) return false;
    add(before.item);
    return true;
  }

  function fillRadioGroup(group, claims, profile, pending, add, handled) {
    for (const r of group) handled.add(r);
    if (group.some((r) => reuse(r, add))) return;
    if (group.some((r) => r.checked)) return;
    const claimed = group.map((r) => claims.get(r)).find(Boolean);
    const key = claimed || AF.matchField({ label: U.groupLabel(group[0]), name: group[0].name }).key;
    const value = valueFor(key, profile);
    if (!key || !value) return;
    const options = group.map((r) => ({ r, label: U.optionLabel(r), value: r.value }));
    const hit = bestOption(options, value);
    if (!hit) return;
    const radio = hit.option.r;
    U.click(radio);
    if (!radio.checked) {
      radio.checked = true;
      radio.dispatchEvent(new Event('input', { bubbles: true }));
      radio.dispatchEvent(new Event('change', { bubbles: true }));
    }
    pending.push(add({
      el: radio, key, kind: 'radio', value, filled: true,
      level: hit.score >= 85 ? 'green' : 'yellow', reason: hit.score >= 85 ? R_PROFILE : R_CLOSE,
      read: (e) => e.checked,
    }));
  }

  // The resume goes only into the resume slot. One file input with no label at all gets it too,
  // marked yellow. Cover letter, photo and transcript slots never get it.
  function fillFiles(inputs, claims, resume, opts, pending, add, handled) {
    const open = [];
    for (const f of inputs) {
      if (f.files && f.files.length) { handled.add(f); reuse(f, add); } else open.push(f);
    }
    for (const el of open) {
      const label = U.labelText(el);
      const hint = label || `${el.name} ${el.id}`;
      let level = null;
      if (NEVER_RE.test(hint)) level = null;
      else if (claims.get(el) === 'resume') level = 'green';
      else if (RESUME_RE.test(hint)) level = 'green';
      else if (inputs.length === 1 && !label) level = 'yellow';
      if (!level) continue;

      if (!resume || !resume.b64) {
        add({ el, key: 'resume', kind: 'file', filled: false, level: 'yellow', reason: opts.resumeError || R_NO_RESUME });
        continue;
      }
      U.setFile(el, resume);
      pending.push(add({
        el, key: 'resume', kind: 'file', value: resume.name, filled: true,
        level, reason: level === 'green' ? R_PROFILE : R_UNLABELED,
        read: (e) => e.files.length === 1 && e.files[0].name === resume.name,
      }));
    }
  }

  async function verify(entry, opts = {}) {
    opts.signal?.throwIfAborted();
    if (!entry.read(entry.el) && opts.fallback && entry.kind === 'text' && typeof chrome !== 'undefined') {
      const attribute = 'data-autofill-target';
      const previous = entry.el.getAttribute(attribute);
      const marker = crypto.randomUUID();
      entry.el.setAttribute(attribute, marker);
      try {
        await chrome.runtime.sendMessage({ type: 'DEBUGGER_FILL', runId: opts.runId, selector: `[${attribute}="${marker}"]`, kind: 'text', value: entry.value });
        entry.el.blur();
        await U.sleep(SETTLE_MS);
      } catch (_) { /* Read-back below remains authoritative when real input fails. */ }
      finally {
        if (previous == null) entry.el.removeAttribute(attribute);
        else entry.el.setAttribute(attribute, previous);
      }
    }
    if (entry.read(entry.el)) {
      filledBefore.set(entry.el, { item: entry, read: entry.read });
      return;
    }
    entry.level = 'yellow';
    entry.reason = R_STUCK;
    entry.filled = false;
  }

  // A required control still empty at the end is yellow with its reason. Counted for the
  // report here; blocking a submit on it is the safety checks' job.
  function requiredPass(all, items, add) {
    const seen = new Set();
    const mark = (el, kind, group = [el]) => {
      const existing = items.find((item) => group.includes(item.el));
      const entry = { el, key: null, kind, filled: false, level: 'yellow', reason: R_REQUIRED };
      if (existing) Object.assign(existing, { filled: false, level: 'yellow', reason: existing.reason || R_REQUIRED });
      else add(entry);
    };
    for (const el of all) {
      if (el.disabled || el.readOnly || !U.isVisible(el)) continue;
      const type = el.tagName === 'INPUT' ? el.type : el.tagName === 'SELECT' ? 'select' : 'textarea';
      if (type === 'file') continue;
      if (type === 'radio') {
        const group = radiosOf(el);
        if (seen.has(group[0])) continue;
        seen.add(group[0]);
        if (group.some(isRequired) && !group.some((r) => r.checked)) mark(group[0], 'radio', group);
        continue;
      }
      if (!isRequired(el)) continue;
      const empty = type === 'checkbox' ? !el.checked : type === 'select' ? !selectHasValue(el) : el.value.trim() === '';
      if (empty) mark(el, type);
    }
  }

  AF.fillPage = fillPage;
  AF.requiredEmptyCount = function (scope) {
    const adapter = AF.adapterFor(root.location.hostname);
    const signInForms = new Set(U.deepQueryAll(scope, 'form').filter(form => adapter.isSignIn(form)));
    const all = U.deepQueryAll(scope, U.CONTROLS)
      .filter(el => !signInForms.has(el.form || el.closest('form')));
    const customEmpty = U.deepQueryAll(scope, '[role=combobox], [aria-haspopup=listbox]')
      .filter(el => !el.disabled && isRequired(el))
      .filter(el => AF.isPlaceholder(U.clean(el.value || el.textContent))).length;
    return missing.length + emptyFiles + customEmpty;
  };
})(globalThis);
