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
    'street-address': 'street',
    'address-line1': 'street',
    'address-level2': 'city',
    'address-level1': 'state',
    'country': 'country',
    'country-name': 'country',
  };

  // Text that names a different field than the keyword it contains ("Referral email", "Phone
  // type", "State your reason"). A vetoed text yields no key at all; it never falls through to a
  // looser rule or to another attribute.
  const NOT_THIS_FIELD = new RegExp([
    '\\b(referr\\w*|emergency|reference|references|recommender|contact (person|name))\\b',
    '\\bphone (type|country|code|extension|ext)\\b',
    '\\b(country|area|dial|calling) code\\b',
    '\\b(state|describe|explain|tell us|share) (your|why|how|about)\\b',
    '\\b(your|the) (reason|answer|story|response)\\b',
    '\\bhear(d)? (about|of)\\b|\\bhow did you (find|hear|learn)\\b',
    '\\bvisa (status|type|category|number)\\b',
  ].join('|'));

  // Order matters: specific keys before generic ones. `test` runs on text from words(); `not`
  // vetoes the key for that text. Keys are the profile keys (helper/store.py MANUAL_KEYS plus the
  // imported fields).
  const FIELD_MATCHERS = [
    { key: 'needsSponsorship', test: /\bsponsor(ship)?\b|\b(require|requires|need|needs) (a |an )?(work )?visa\b/ },
    {
      key: 'workAuthorization',
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
      key: 'street',
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
    if (!w) return undefined;
    if (NOT_THIS_FIELD.test(w)) return null;
    for (const m of FIELD_MATCHERS) {
      if (m.test.test(w) && !(m.not && m.not.test(w))) return m.key;
    }
    return undefined;
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
      if (key === null) return { key: null, questionStyle };
      if (key) return { key, questionStyle };
    }
    return { key: null, questionStyle };
  }

  const api = { matchField, isQuestionStyle, FIELD_MATCHERS, AUTOCOMPLETE };
  root.AF = root.AF || {};
  Object.assign(root.AF, api);
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(globalThis);
