// Generic field matcher: label/name/placeholder patterns -> profile key. Classic script (load
// order: scorer.js, matcher.js, main.js); attaches to globalThis.AF and exports for unit tests.
(function (root) {
  'use strict';

  // Lowercase, split camelCase, turn every non-alphanumeric run into one space.
  function words(s) {
    return String(s == null ? '' : s)
      .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
      .toLowerCase()
      .replace(/['\u2019]/g, '')
      .replace(/[^a-z0-9]+/g, ' ')
      .trim();
  }

  // autocomplete tokens (HTML autofill field names)
  const AUTOCOMPLETE = {
    'given-name': 'firstName',
    'family-name': 'lastName',
    'name': 'fullName',
    'email': 'email',
    'tel': 'phone',
    'tel-national': 'phone',
    'postal-code': 'zip',
    'street-address': 'address',
    'address-line1': 'address',
    'address-level2': 'city',
    'address-level1': 'state',
    'country': 'country',
    'country-name': 'country',
  };

  // Order matters: specific keys before generic ones. `test` runs on text from words(); `not`
  // vetoes the key for that text.
  const FIELD_MATCHERS = [
    { key: 'sponsorship', test: /\bsponsor(ship)?\b|\bvisa\b/ },
    {
      key: 'workAuth',
      test: /\b(authori[sz]ed|eligible|legally entitled|legal right|right) to work\b|\bwork (authori[sz]ation|permit|eligibility|status)\b/,
    },
    { key: 'email', test: /\be ?mail\b/ },
    { key: 'phone', test: /\b(phone|telephone|mobile|cell|cellphone|tel)\b/ },
    { key: 'firstName', test: /\b(first name|given name|forename|fname)\b/ },
    { key: 'lastName', test: /\b(last name|family name|surname|lname)\b/ },
    { key: 'fullName', test: /^((your|full|legal|candidate|applicant) )*name$|\bfull name\b|\blegal name\b|\byour name\b/ },
    { key: 'linkedin', test: /\blinked ?in\b/ },
    { key: 'github', test: /\bgit ?hub\b/ },
    { key: 'website', test: /\b(website|web site|portfolio|personal (site|url|page)|homepage|home page|blog)\b/ },
    { key: 'zip', test: /\b(zip|zipcode|postal code|postcode|post code)\b/ },
    { key: 'city', test: /\b(city|town)\b/ },
    { key: 'country', test: /\bcountry\b|\bnation\b/ },
    { key: 'state', test: /\b(state|province|region)\b/ },
    {
      key: 'address',
      test: /\b(street|address|address line|addr)\b/,
      not: /\b(line|address) ?(2|two)\b|\b(apt|apartment|suite|unit)\b/,
    },
    { key: 'gender', test: /\b(gender|sex)\b/ },
    { key: 'race', test: /\b(race|ethnicity|ethnic)\b/ },
    { key: 'veteran', test: /\b(veteran|military)\b/ },
    { key: 'disability', test: /\bdisabilit(y|ies)\b/ },
  ];

  function matchText(text) {
    const w = words(text);
    if (!w) return null;
    for (const m of FIELD_MATCHERS) {
      if (m.test.test(w) && !(m.not && m.not.test(w))) return m.key;
    }
    return null;
  }

  function isQuestionStyle(label) {
    const s = String(label == null ? '' : label).trim();
    if (!s) return false;
    return s.includes('?') || s.split(/\s+/).length > 6;
  }

  // ctx: {label, name, id, placeholder, autocomplete, automationId}
  // -> {key: string|null, questionStyle: boolean}. questionStyle is about the visible label only.
  function matchField(ctx) {
    ctx = ctx || {};
    const questionStyle = isQuestionStyle(ctx.label);

    for (const tok of String(ctx.autocomplete || '').toLowerCase().split(/\s+/)) {
      if (Object.prototype.hasOwnProperty.call(AUTOCOMPLETE, tok)) return { key: AUTOCOMPLETE[tok], questionStyle };
    }
    // The visible label is authoritative; attributes are only consulted when it says nothing.
    for (const src of [ctx.label, ctx.placeholder, ctx.name, ctx.id, ctx.automationId]) {
      const key = matchText(src);
      if (key) return { key, questionStyle };
    }
    return { key: null, questionStyle };
  }

  const api = { matchField, isQuestionStyle, FIELD_MATCHERS };
  root.AF = root.AF || {};
  Object.assign(root.AF, api);
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(globalThis);
