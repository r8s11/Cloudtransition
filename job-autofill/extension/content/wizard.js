// Passive step observer. It never clicks navigation or submission controls.
// start(runCtx), stop(), onStep(cb) -> unsubscribe, fingerprint() -> FNV-1a hex.
// Callbacks receive {runCtx, step, fingerprint}; start records the already-filled first step.
(function (root) {
  'use strict';
  const AF = (root.AF = root.AF || {});
  if (AF.wizard) return;
  const callbacks = new Set();
  let observer = null;
  let timer = null;
  let context = null;
  let step = 1;
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
    timer = null;
    context = null;
  }

  function start(runCtx) {
    stop();
    context = runCtx;
    step = 1;
    seen.clear();
    seen.add(fingerprint());
    observer = new MutationObserver(() => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        if (!context) return;
        const fp = fingerprint();
        if (seen.has(fp)) return;
        seen.add(fp);
        step += 1;
        for (const cb of callbacks) cb({ runCtx: context, step, fingerprint: fp });
      }, 850);
    });
    observer.observe(document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ['hidden', 'style', 'class', 'aria-hidden'] });
  }

  AF.wizard = { start, stop, fingerprint, onStep(cb) { callbacks.add(cb); return () => callbacks.delete(cb); } };
})(globalThis);
