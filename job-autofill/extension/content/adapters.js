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

  // Defaults every adapter shares.
  function adapter(spec) {
    return Object.assign({
      name: 'generic',
      hosts: [],
      fields: () => [],
      isSignIn: (scope) => U.deepQueryAll(scope, 'input[type=password]').some(U.isVisible),
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
