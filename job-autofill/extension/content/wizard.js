// Settled semantic steps, bounded navigation, and idle lifetime.
// onStep receives {runCtx, step, fingerprint}; onStop receives a reason and code.
(function (root) {
  'use strict';
  const AF = (root.AF = root.AF || {});
  if (AF.wizard) return;
  const callbacks = new Set();
  let observer = null;
  let timer = null;
  let idle = null;
  let advanceTimer = null;
  let context = null;
  let step = 1;
  let current = '';
  const seen = new Set();

  function fingerprint() {
    const U = AF.util;
    const controls = U.deepQueryAll(document, 'input, select, textarea, [role=combobox], [data-automation-id=file-upload-drop-zone]')
      .filter((el) => !el.closest('#autofill-hud') && (el.type === 'file' || U.isVisible(el)))
      .map((el) => [el.tagName, el.type || '', el.id, el.name || '', el.getAttribute('data-automation-id') || '', U.labelText(el)].join('|'));
    const headings = U.deepQueryAll(document, 'h1, h2, [role=heading]').filter(U.isVisible).map((el) => U.clean(el.textContent));
    const text = [location.pathname, ...headings, ...controls].join('\n');
    let hash = 0x811c9dc5;
    for (let i = 0; i < text.length; i += 1) hash = Math.imul(hash ^ text.charCodeAt(i), 0x01000193) >>> 0;
    return hash.toString(16).padStart(8, '0');
  }

  function stop() {
    observer?.disconnect();
    observer = null;
    clearTimeout(timer);
    clearTimeout(idle);
    clearTimeout(advanceTimer);
    timer = idle = advanceTimer = null;
    context = null;
  }
  function end(reason, code) {
    const ctx = context;
    stop();
    ctx?.onStop(reason, code);
  }
  function resetIdle() {
    clearTimeout(idle);
    idle = setTimeout(() => end('5-minute idle limit', 'idle'), 300000);
  }
  function settled() {
    if (!context) return;
    const fp = fingerprint();
    if (fp === current) {
      if (advanceTimer) end("page didn't advance", 'no_advance');
      return;
    }
    clearTimeout(advanceTimer);
    advanceTimer = null;
    if (seen.has(fp)) return end("page didn't advance", 'no_advance');
    if (step >= 10) return end('10-step limit', 'limit');
    seen.add(fp);
    current = fp;
    step += 1;
    resetIdle();
    for (const cb of callbacks) cb({ runCtx: context, step, fingerprint: fp });
  }
  function start(runCtx) {
    stop();
    context = runCtx;
    step = 1;
    current = fingerprint();
    seen.clear();
    seen.add(current);
    resetIdle();
    observer = new MutationObserver(records => {
      if (records.every(r => r.target.closest?.('#autofill-hud'))) return;
      clearTimeout(timer);
      timer = setTimeout(settled, 850);
    });
    observer.observe(document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ['hidden', 'style', 'class', 'aria-hidden'] });
  }
  function advancing() {
    clearTimeout(advanceTimer);
    advanceTimer = setTimeout(settled, 850);
  }
  AF.wizard = { start, stop, advancing, fingerprint, onStep(cb) { callbacks.add(cb); return () => callbacks.delete(cb); } };
})(globalThis);
