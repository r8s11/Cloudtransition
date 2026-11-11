// Page helpers shared by the content scripts: Shadow DOM walker, visibility, label extraction,
// native value setter, click sequence, file input. Classic script; attaches to globalThis.AF.util.
(function (root) {
  'use strict';
  const AF = (root.AF = root.AF || {});

  const CONTROLS = 'input, select, textarea';

  // Every match under `scope`, including inside open shadow roots.
  function deepQueryAll(scope, selector, out) {
    out = out || [];
    for (const el of scope.querySelectorAll(selector)) out.push(el);
    for (const host of scope.querySelectorAll('*')) {
      if (host.shadowRoot) deepQueryAll(host.shadowRoot, selector, out);
    }
    return out;
  }

  function isVisible(el) {
    if (!el || !el.isConnected) return false;
    const view = el.ownerDocument.defaultView || root;
    const st = view.getComputedStyle(el);
    if (st.display === 'none' || st.visibility === 'hidden') return false;
    return el.getClientRects().length > 0;
  }

  function clean(s) {
    return String(s == null ? '' : s)
      .replace(/\s+/g, ' ')
      .replace(/[\s*\u2731]+$/, '')
      .replace(/\s*\(required\)$/i, '')
      .trim();
  }

  // Text of a node without the form controls and scripts inside it.
  function textWithoutControls(node) {
    const c = node.cloneNode(true);
    for (const n of c.querySelectorAll('input, select, textarea, button, script, style, option, svg')) n.remove();
    return c.textContent || '';
  }

  function byIds(el, ids) {
    const scope = el.getRootNode();
    const out = [];
    for (const id of String(ids || '').split(/\s+/)) {
      const n = id && scope.getElementById ? scope.getElementById(id) : null;
      if (n) out.push(textWithoutControls(n));
    }
    return out.join(' ');
  }

  function distinctControls(node) {
    const names = new Set();
    let n = 0;
    for (const c of node.querySelectorAll('input:not([type=hidden]), select, textarea')) {
      if (c.type === 'radio' && c.name) names.add('r:' + c.name);
      else n += 1;
    }
    return n + names.size;
  }

  // Label sitting next to a control inside a small wrapper that holds only that control.
  function wrapperLabel(el) {
    let node = el.parentElement;
    for (let i = 0; i < 4 && node; i += 1, node = node.parentElement) {
      if (distinctControls(node) > 1) break;
      for (const lab of node.querySelectorAll('label, legend, .label, [class*="label"], [data-label]')) {
        if (lab.contains(el)) continue;
        const forId = lab.getAttribute && lab.getAttribute('for');
        if (forId && forId !== el.id) continue;
        const t = clean(textWithoutControls(lab));
        if (t) return t;
      }
    }
    return '';
  }

  // Visible question text for a control.
  function labelText(el) {
    const lb = clean(byIds(el, el.getAttribute('aria-labelledby')));
    if (lb) return lb;
    if (el.labels && el.labels.length) {
      const t = clean(Array.from(el.labels).map(textWithoutControls).join(' '));
      if (t) return t;
    }
    const al = clean(el.getAttribute('aria-label'));
    if (al) return al;
    return wrapperLabel(el);
  }

  // Question text for a radio group: legend, group aria label, or the wrapper's label.
  function groupLabel(radio) {
    const group = radio.closest('[role=radiogroup], [role=group]');
    if (group) {
      const t = clean(byIds(group, group.getAttribute('aria-labelledby')) || group.getAttribute('aria-label'));
      if (t) return t;
    }
    const fs = radio.closest('fieldset');
    if (fs) {
      const lg = fs.querySelector('legend');
      if (lg) { const t = clean(textWithoutControls(lg)); if (t) return t; }
    }
    return wrapperLabel(radio);
  }

  // Text of one radio option.
  function optionLabel(radio) {
    const lb = clean(byIds(radio, radio.getAttribute('aria-labelledby')));
    if (lb) return lb;
    if (radio.labels && radio.labels.length) {
      const t = clean(Array.from(radio.labels).map(textWithoutControls).join(' '));
      if (t) return t;
    }
    return clean(radio.getAttribute('aria-label')) || radio.value || '';
  }

  function fire(el, type, Ctor, init) {
    el.dispatchEvent(new Ctor(type, Object.assign({ bubbles: true, cancelable: true, composed: true }, init)));
  }

  // Sets the value through the prototype's own setter (what a framework-controlled input
  // expects), then sends focus, input, change and blur.
  function setNative(el, value) {
    const proto = el instanceof root.HTMLTextAreaElement ? root.HTMLTextAreaElement.prototype
      : el instanceof root.HTMLSelectElement ? root.HTMLSelectElement.prototype
        : root.HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
    fire(el, 'focus', root.FocusEvent, { bubbles: false, cancelable: false });
    setter.call(el, value);
    fire(el, 'input', root.InputEvent, { inputType: 'insertText', data: String(value), cancelable: false });
    fire(el, 'change', root.Event);
    fire(el, 'blur', root.FocusEvent, { bubbles: false, cancelable: false });
  }

  // Pointer and mouse sequence ending in a click.
  function click(el) {
    const init = { view: root, button: 0 };
    for (const t of ['pointerdown', 'mousedown', 'pointerup', 'mouseup']) {
      fire(el, t, t.startsWith('pointer') ? root.PointerEvent : root.MouseEvent, init);
    }
    el.click();
  }

  function fileFrom(res) {
    const bin = root.atob(res.b64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i += 1) bytes[i] = bin.charCodeAt(i);
    return new root.File([bytes], res.name, { type: res.type || 'application/pdf' });
  }

  function setFile(input, res) {
    const dt = new root.DataTransfer();
    dt.items.add(fileFrom(res));
    input.files = dt.files;
    fire(input, 'input', root.Event, { cancelable: false });
    fire(input, 'change', root.Event);
  }

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  AF.util = {
    CONTROLS, deepQueryAll, isVisible, clean, textWithoutControls, labelText, groupLabel,
    optionLabel, setNative, click, setFile, fileFrom, sleep,
  };
})(globalThis);
