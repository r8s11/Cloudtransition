// Field highlights and the page panel. Classic script; attaches to globalThis.AF.
//
//   AF.highlight(el, level, reason)   level 'green' | 'yellow'; 2px border + soft ring + title
//   AF.clearHighlights()              puts back each element's own border, box-shadow and title
//   AF.hud.render(summary, handlers)  panel in a Shadow DOM, top frame only
//     summary: {title?, counts?: {green, yellow, filled}, review?: [{label, reason}],
//               message?, tone?: 'rv'|'stop'|'done', badge?, canStop?, runId?}
//     handlers: {onStop?}
(function (root) {
  'use strict';
  const AF = (root.AF = root.AF || {});
  const U = AF.util;

  const COLORS = {
    green: { border: '#16a34a', ring: 'rgba(22, 163, 74, 0.16)' },
    yellow: { border: '#ca8a04', ring: 'rgba(202, 138, 4, 0.22)' },
  };
  const PREFIX = 'AutoFill: ';

  // element -> what it had before the first highlight
  const saved = new Map();

  // A control hidden behind a styled button shows its border on the nearest visible ancestor.
  function targetOf(el) {
    let node = el;
    for (let i = 0; i < 3 && node && !U.isVisible(node); i += 1) node = node.parentElement;
    return node && U.isVisible(node) ? node : el;
  }

  function highlight(el, level, reason) {
    const c = COLORS[level];
    if (!c || !el) return;
    const t = targetOf(el);
    if (!saved.has(t)) {
      saved.set(t, {
        border: [t.style.getPropertyValue('border'), t.style.getPropertyPriority('border')],
        shadow: [t.style.getPropertyValue('box-shadow'), t.style.getPropertyPriority('box-shadow')],
        title: t.getAttribute('title'),
      });
    }
    t.style.setProperty('border', `2px solid ${c.border}`, 'important');
    t.style.setProperty('box-shadow', `0 0 0 2px ${c.ring}`, 'important');
    if (reason) t.setAttribute('title', String(reason).startsWith(PREFIX) ? reason : PREFIX + reason);
  }

  function clearHighlights() {
    for (const [t, o] of saved) {
      if (o.border[0]) t.style.setProperty('border', o.border[0], o.border[1]);
      else t.style.removeProperty('border');
      if (o.shadow[0]) t.style.setProperty('box-shadow', o.shadow[0], o.shadow[1]);
      else t.style.removeProperty('box-shadow');
      if (o.title == null) t.removeAttribute('title');
      else t.setAttribute('title', o.title);
    }
    saved.clear();
  }

  // ---- panel ---------------------------------------------------------------------------
  const CSS = `
    :host { all: initial; }
    * { box-sizing: border-box; font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif; }
    .wrap { position: fixed; right: 16px; bottom: 16px; z-index: 2147483647; }
    .panel { width: 320px; background: #171512; color: #f4ead8; border-radius: 10px; border: 1px solid #3a352d; box-shadow: 0 10px 25px rgba(0,0,0,.35); padding: 10px 12px; font-size: 12.5px; line-height: 1.4; }
    .top { display: flex; justify-content: space-between; align-items: center; }
    .t { font-weight: 700; display: flex; gap: 6px; align-items: center; }
    .t i { width: 10px; height: 10px; background: #b3212e; transform: rotate(45deg); display: inline-block; }
    button { font: inherit; cursor: pointer; }
    .x { background: none; border: none; color: #b8ad9a; padding: 0 4px; font-size: 14px; }
    .cpill { display: flex; gap: 6px; margin-top: 6px; flex-wrap: wrap; }
    .cpill span { font-size: 11px; font-weight: 600; padding: 1px 7px; border-radius: 999px; border: 1px solid; }
    .g { color: #86efac; border-color: #22c55e; } .y { color: #fde047; border-color: #eab308; } .b { color: #fca5a5; border-color: #b3212e; }
    ul { list-style: none; margin: 8px 0 0; padding: 0; display: grid; gap: 3px; }
    li { display: grid; grid-template-columns: 16px 1fr; gap: 6px; font-size: 12px; color: #e6dccb; }
    li .ic { color: #facc15; font-weight: 700; }
    .reason { margin-top: 8px; padding: 6px 8px; border-radius: 6px; font-size: 12px; }
    .reason.rv { background: rgba(202,138,4,.18); color: #fde68a; }
    .reason.stop { background: rgba(179,33,46,.28); color: #fecaca; }
    .reason.done { background: rgba(22,163,74,.2); color: #bbf7d0; }
    .btns { display: flex; gap: 6px; margin-top: 10px; }
    .btns button { background: #2a2620; color: #f4ead8; border: 1px solid #4a443a; border-radius: 6px; min-height: 28px; padding: 2px 10px; font-size: 12px; font-weight: 600; }
    .pill { display: none; align-items: center; gap: 8px; background: #171512; color: #f4ead8; border: none; border-radius: 999px; padding: 6px 12px; font-size: 12px; font-weight: 600; box-shadow: 0 6px 16px rgba(0,0,0,.3); }
    button:focus-visible { outline: 2px solid #fde047; outline-offset: 2px; }
    @media (max-width: 899px) {
      .pill { display: inline-flex; }
      .panel { display: none; }
      .wrap.open .panel { display: block; }
      .wrap.open .pill { display: none; }
    }
  `;

  let host = null;
  let shadow = null;
  let wrapEl = null;
  let lastRunId = null;
  let dismissed = false;
  let open = false;
  let last = null;
  let lastHandlers = {};

  function ensure() {
    if (host && host.isConnected) return;
    host = document.createElement('div');
    host.id = 'autofill-hud';
    shadow = host.attachShadow({ mode: 'open' });
    const style = document.createElement('style');
    style.textContent = CSS;
    wrapEl = document.createElement('div');
    wrapEl.className = 'wrap';
    shadow.append(style, wrapEl);
    (document.body || document.documentElement).appendChild(host);
  }

  function el(tag, props, ...kids) {
    const n = document.createElement(tag);
    Object.assign(n, props || {});
    n.append(...kids);
    return n;
  }

  function pillText(s) {
    const c = s.counts || {};
    const parts = ['\u25c6 AutoFill'];
    if (c.filled != null) parts.push(`${c.filled} filled`);
    if (c.yellow) parts.push(`${c.yellow} to review`);
    if (!parts[1] && s.message) parts.push(s.message);
    return parts.join(' \u00b7 ');
  }

  function draw() {
    const s = last;
    wrapEl.className = 'wrap' + (open ? ' open' : '');
    wrapEl.textContent = '';
    const c = s.counts || {};

    const panel = el('div', { className: 'panel', role: 'status' });
    panel.setAttribute('aria-live', 'polite');
    const title = s.title || (c.filled != null ? `AutoFill \u00b7 ${c.filled} filled` : 'AutoFill');
    const close = el('button', { className: 'x', type: 'button', textContent: '\u2715' });
    close.setAttribute('aria-label', 'Dismiss');
    close.addEventListener('click', () => { dismissed = true; open = false; draw(); });
    panel.append(el('div', { className: 'top' }, el('div', { className: 't' }, el('i'), title), close));

    const chips = el('div', { className: 'cpill' });
    if (c.green) chips.append(el('span', { className: 'g', textContent: `\u2713 ${c.green} from profile` }));
    if (c.yellow) chips.append(el('span', { className: 'y', textContent: `! ${c.yellow} to review` }));
    if (s.badge) chips.append(el('span', { className: 'b', textContent: s.badge }));
    if (chips.childNodes.length) panel.append(chips);

    if (s.review && s.review.length) {
      const list = el('ul');
      for (const r of s.review.slice(0, 5)) {
        list.append(el('li', {}, el('span', { className: 'ic', textContent: '!' }), `${r.label ? r.label + ' \u2014 ' : ''}${r.reason}`));
      }
      if (s.review.length > 5) list.append(el('li', {}, el('span'), `and ${s.review.length - 5} more`));
      panel.append(list);
    }
    if (s.message) panel.append(el('div', { className: `reason ${s.tone || 'rv'}`, textContent: s.message }));

    const btns = el('div', { className: 'btns' });
    const clear = el('button', { type: 'button', textContent: 'Clear borders' });
    clear.addEventListener('click', () => clearHighlights());
    btns.append(clear);
    if (s.canStop && lastHandlers.onStop) {
      const stop = el('button', { type: 'button', textContent: 'Stop' });
      stop.addEventListener('click', () => lastHandlers.onStop());
      btns.append(stop);
    }
    panel.append(btns);

    const pill = el('button', { className: 'pill', type: 'button', textContent: pillText(s) });
    pill.addEventListener('click', () => { open = true; draw(); });
    wrapEl.append(panel, pill);
    wrapEl.style.display = dismissed ? 'none' : '';
  }

  // Top frame only: every other frame reports through the background instead.
  function render(summary, handlers) {
    if (root.top !== root) return false;
    if (summary.runId && summary.runId !== lastRunId) { lastRunId = summary.runId; dismissed = false; open = false; }
    ensure();
    last = summary;
    lastHandlers = handlers || lastHandlers;
    draw();
    return true;
  }

  function remove() {
    if (host) host.remove();
    host = null;
  }

  AF.highlight = highlight;
  AF.clearHighlights = clearHighlights;
  AF.hud = { render, remove };
})(globalThis);
