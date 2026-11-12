// Pure gate shared by page snapshots and the final pre-click check.
(function (root) {
  'use strict';
  const AF = root.AF = root.AF || {};
  AF.safetyCheck = function (state) {
    const fail = (reason, code) => ({ ok: false, reason, code });
    if (state.captcha) return fail(`${state.captcha} detected — finish and submit yourself`, 'captcha');
    const review = Math.max(state.yellow || 0, state.aiDrafts || 0);
    if (review) return fail(`${review} field${review === 1 ? '' : 's'} to review`, 'review');
    if (state.required) return fail(`${state.required} required field${state.required === 1 ? '' : 's'} empty`, 'required');
    if (state.readback) return fail('readback', 'readback');
    if (!state.button) return fail('No safe Next or Submit button found', 'button');
    if (state.submitted) return fail('Already submitted from this tab', 'duplicate');
    return { ok: true, reason: '', code: '' };
  };
  AF.safeButton = function (adapter, scope = document) {
    const H = AF.adapterHelpers;
    const forbidden = /\b(back|previous|cancel|save (as )?draft|upload|sign[ -]?in|log[ -]?in|create (an? )?account|with (linkedin|indeed|google))\b/i;
    for (const [kind, method, pattern] of [
      ['next', 'nextButton', /^(next|continue|save (and|&) continue)\b/i],
      ['submit', 'submitButton', /^(submit|apply|send application)\b/i],
    ]) {
      const valid = el => el && AF.util.isVisible(el) && !el.disabled && !forbidden.test(H.buttonText(el))
        && !adapter.isSignIn(el.closest('form') || scope);
      const preferred = adapter[method]?.(scope);
      const el = valid(preferred) ? preferred : H.buttons(scope).find(button => pattern.test(H.buttonText(button)) && valid(button));
      if (el) return { kind, el };
    }
    return null;
  };
  AF.captcha = function () {
    const nodes = AF.util.deepQueryAll(document, 'iframe, [class], [id], [data-sitekey]');
    for (const [name, re] of [['reCAPTCHA', /recaptcha/i], ['hCaptcha', /hcaptcha/i], ['Turnstile', /turnstile|challenges\.cloudflare/i], ['Arkose', /arkose|funcaptcha/i]]) {
      if (nodes.some(el => re.test([el.id, el.className, el.getAttribute('src') || ''].join(' ')))) return name;
    }
    return '';
  };
  AF.confirmed = function (adapter) {
    const text = AF.util.textWithoutControls(document.body);
    return [...(adapter.confirm?.text || []), /thank you for (applying|your application)/i, /application (was )?(submitted|received)/i].some(re => re.test(text))
      || (adapter.confirm?.paths || []).some(re => re.test(location.pathname));
  };
})(globalThis);
