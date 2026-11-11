// Per-site adapters. An adapter claims fields by stable markers (ids, names); the generic label
// matcher in fill.js handles everything an adapter did not claim, and is the only matcher on
// other hosts. Classic script; attaches to globalThis.AF.
//
//   AF.adapterFor(hostname) -> {name, fields(root) -> [{el, key}], isSignIn(root),
//                               confirm: {paths: [RegExp], text: [RegExp]},
//                               nextButton(root), submitButton(root)}
//   AF.registerAdapter(adapter)   adapter.hosts is a list of RegExp tested against the hostname.
(function (root) {
  'use strict';
  const AF = (root.AF = root.AF || {});
  const U = AF.util;

  const registry = [];

  function claim(scope, map) {
    const out = [];
    for (const [selector, key] of map) {
      for (const el of U.deepQueryAll(scope, selector)) out.push({ el, key });
    }
    return out;
  }

  function buttons(scope) {
    return U.deepQueryAll(scope, 'button, input[type=submit], input[type=button], a[role=button]')
      .filter((b) => U.isVisible(b) && !b.disabled);
  }

  function buttonText(b) {
    return U.clean(b.value || b.getAttribute('aria-label') || b.textContent || '');
  }

  function findButton(scope, re) {
    return buttons(scope).find((b) => re.test(buttonText(b))) || null;
  }

  const BACK = /\b(back|previous|cancel|save (as )?draft|upload|sign in|log in)\b/i;

  const AUTH_TITLE = /^(sign in|log in|create (an? )?account)$/i;
  const NAVIGATION = 'header, nav, footer, aside, [role=navigation]';

  function isAuthForm(form) {
    if (U.deepQueryAll(form, 'input[type=password]').length) return true;
    const label = U.clean(form.getAttribute('aria-label') || '');
    const labelledBy = (form.getAttribute('aria-labelledby') || '').split(/\s+/)
      .map((id) => form.ownerDocument.getElementById(id)?.textContent || '').join(' ');
    if ([label, U.clean(labelledBy)].some((text) => AUTH_TITLE.test(text))) return true;

    // Only a form's own headings and native actions classify it; navigation links do not.
    const headings = U.deepQueryAll(form, 'h1, h2, h3, legend')
      .filter((el) => U.isVisible(el) && el.closest('form') === form);
    if (headings.some((el) => AUTH_TITLE.test(U.clean(el.textContent)))) return true;
    const actions = buttons(form).filter((el) => el.tagName !== 'A' && el.closest('form') === form && el.type !== 'reset');
    const primary = actions.findLast((el) => el.type === 'submit') || actions.at(-1);
    if (primary && AUTH_TITLE.test(buttonText(primary))) return true;

    // Email-first sign-in pages often put the page heading just before the form.
    // A form's own heading takes precedence over surrounding page text.
    if (headings.length) return false;
    const section = form.closest('section, main, article, [role=main]') || form.parentElement;
    if (!section) return false;
    const preceding = U.deepQueryAll(section, 'h1, h2, h3')
      .filter((el) => U.isVisible(el) && !el.closest('form') && !el.closest(NAVIGATION)
        && (el.compareDocumentPosition(form) & root.Node.DOCUMENT_POSITION_FOLLOWING));
    return !!preceding.length && AUTH_TITLE.test(U.clean(preceding.at(-1).textContent));
  }

  function isSignIn(scope) {
    if (scope.matches?.('form')) return isAuthForm(scope);
    const forms = U.deepQueryAll(scope, 'form');
    return forms.length ? forms.every(isAuthForm) : U.deepQueryAll(scope, 'input[type=password]').length > 0;
  }

  // Defaults every adapter shares.
  function adapter(spec) {
    return Object.assign({
      name: 'generic',
      hosts: [],
      fields: () => [],
      isSignIn,
      confirm: { paths: [], text: [] },
      nextButton: (scope) => {
        const b = findButton(scope, /^(next|continue|save (and|&) continue)\b/i);
        return b && !BACK.test(buttonText(b)) ? b : null;
      },
      submitButton: (scope) => {
        const b = findButton(scope, /^(submit|apply|send application|submit application)\b/i);
        return b && !BACK.test(buttonText(b)) ? b : null;
      },
    }, spec);
  }

  function registerAdapter(spec) {
    const a = adapter(spec);
    registry.push(a);
    return a;
  }

  const generic = adapter({});

  registerAdapter({
    name: 'greenhouse',
    hosts: [/(^|\.)greenhouse\.io$/],
    fields: (scope) => claim(scope, [
      ['#first_name', 'firstName'],
      ['#last_name', 'lastName'],
      ['#email', 'email'],
      ['#phone', 'phone'],
      ['#candidate-location', 'location'],
      ['input[type=file]#resume, input[type=file][name=resume]', 'resume'],
      ['#gender', 'gender'],
      ['#race', 'race'],
      ['#veteran_status', 'veteran'],
      ['#disability_status', 'disability'],
    ]),
    confirm: {
      paths: [/\/confirmation\b/i, /\/thanks?\b/i],
      text: [/thank you for applying/i, /application (has been )?(submitted|received)/i],
    },
  });

  registerAdapter({
    name: 'lever',
    hosts: [/^jobs\.lever\.co$/],
    fields: (scope) => claim(scope, [
      ['input[name=name]', 'fullName'],
      ['input[name=email]', 'email'],
      ['input[name=phone]', 'phone'],
      ['input[name="urls[LinkedIn]"]', 'linkedin'],
      ['input[name="urls[GitHub]"]', 'github'],
      ['input[name="urls[Portfolio]"]', 'website'],
      ['input[type=file][name=resume]', 'resume'],
    ]),
    confirm: {
      paths: [/\/thanks\b/i],
      text: [/application (has been )?(submitted|received)/i, /thank you for applying/i],
    },
  });

  // Native fields use stable vendor markers; custom widgets share the fill engine's scorer.
  const combos = (scope) => U.deepQueryAll(scope, '[role=combobox], [aria-haspopup=listbox], [data-automation-id=selectWidget]')
    .filter((el) => el.tagName !== 'SELECT')
    .map((el) => ({ el, key: AF.matchField({ label: U.labelText(el), name: el.name || '' }).key, kind: 'combo' }));

  registerAdapter({
    name: 'ashby',
    hosts: [/^jobs\.ashbyhq\.com$/],
    fields: (scope) => claim(scope, [
      ['[name="_systemfield_name"]', 'fullName'], ['[name="_systemfield_email"]', 'email'],
      ['[name="_systemfield_phone"]', 'phone'],
    ]),
    widgets: combos,
  });

  registerAdapter({
    name: 'workday',
    hosts: [/(^|\.)myworkdayjobs\.com$/],
    fields: (scope) => claim(scope, [
      ['[data-automation-id="legalNameSection_firstName"]', 'firstName'],
      ['[data-automation-id="legalNameSection_lastName"]', 'lastName'],
      ['[data-automation-id="email"]', 'email'], ['[data-automation-id="phone-number"]', 'phone'],
      ['[data-automation-id="addressSection_city"]', 'city'],
      ['[data-automation-id="addressSection_postalCode"]', 'zip'],
      ['[data-automation-id="gender"]', 'gender'],
    ]),
    widgets: (scope) => [...combos(scope), ...U.deepQueryAll(scope, '[data-automation-id="file-upload-drop-zone"]')
      .map((el) => ({ el, key: 'resume', kind: 'drop' }))],
    nextButton: (scope) => U.deepQueryAll(scope, '[data-automation-id="bottom-navigation-next-button"]')
      .find((el) => U.isVisible(el) && !el.disabled) || null,
  });

  registerAdapter({
    name: 'icims',
    hosts: [/(^|\.)icims\.com$/],
    fields: (scope) => claim(scope, [
      ['[id="PersonProfileFields.FirstName"]', 'firstName'],
      ['[id="PersonProfileFields.LastName"]', 'lastName'],
      ['[id="PersonProfileFields.Email"]', 'email'],
      ['[id="PersonProfileFields.PhoneNumber"]', 'phone'],
      ['input[type=file][name*=resume i]', 'resume'],
    ]),
  });

  registerAdapter({
    name: 'indeed',
    hosts: [/(^|\.)indeed\.com$/],
    fields: (scope) => claim(scope, [
      ['[name="fullName"]', 'fullName'], ['[name="firstName"]', 'firstName'],
      ['[name="lastName"]', 'lastName'], ['[name="email"]', 'email'],
      ['[name="phoneNumber"]', 'phone'], ['input[type=file][name="resume"]', 'resume'],
      ['input[type=radio][name="workAuthorization"]', 'workAuthorization'],
      ['input[type=radio][name="needsSponsorship"]', 'needsSponsorship'],
    ]),
  });

  // Fixtures are served from 127.0.0.1, so a page there may name its adapter in
  // <meta name="autofill-test-ats" content="greenhouse">. The meta is honored ONLY on
  // 127.0.0.1 and localhost; on any real host it is ignored.
  function testOverride(host) {
    if (host !== '127.0.0.1' && host !== 'localhost') return null;
    const meta = root.document && root.document.querySelector('meta[name="autofill-test-ats"]');
    const name = meta && meta.getAttribute('content');
    return registry.find((a) => a.name === name) || null;
  }

  function adapterFor(host) {
    host = String(host || '').toLowerCase();
    return testOverride(host) || registry.find((a) => a.hosts.some((re) => re.test(host))) || generic;
  }

  AF.adapterFor = adapterFor;
  AF.registerAdapter = registerAdapter;
  AF.adapterHelpers = { claim, buttons, buttonText, findButton };
})(globalThis);
