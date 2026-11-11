// Option scorer and alias dictionary. Classic script: attaches to globalThis.AF (MV3 content
// scripts are not modules) and also exports through module.exports for the unit tests.
(function (root) {
  'use strict';

  // Lowercase, strip accents and apostrophes, turn every other non-alphanumeric run into one space.
  function norm(s) {
    return String(s == null ? '' : s)
      .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .replace(/['\u2019]/g, '')
      .replace(/[^a-z0-9]+/g, ' ')
      .trim();
  }

  // ---- Alias groups -------------------------------------------------------------------
  // A group is a set of normalized phrases that all mean the same thing. Groups in the same
  // family compete: when an option text matches a rival group better than the target's group
  // ("Female" for target "Male", "West Virginia" for target "Virginia"), it scores 0.
  const GROUPS = [];
  function group(family, phrases) {
    const set = new Set();
    for (const p of phrases) { const n = norm(p); if (n) set.add(n); }
    GROUPS.push({ family, set });
  }

  const STATES = [
    ['AL', 'Alabama'], ['AK', 'Alaska'], ['AZ', 'Arizona'], ['AR', 'Arkansas'],
    ['CA', 'California'], ['CO', 'Colorado'], ['CT', 'Connecticut'], ['DE', 'Delaware'],
    ['FL', 'Florida'], ['GA', 'Georgia'], ['HI', 'Hawaii'], ['ID', 'Idaho'],
    ['IL', 'Illinois'], ['IN', 'Indiana'], ['IA', 'Iowa'], ['KS', 'Kansas'],
    ['KY', 'Kentucky'], ['LA', 'Louisiana'], ['ME', 'Maine'], ['MD', 'Maryland'],
    ['MA', 'Massachusetts'], ['MI', 'Michigan'], ['MN', 'Minnesota'], ['MS', 'Mississippi'],
    ['MO', 'Missouri'], ['MT', 'Montana'], ['NE', 'Nebraska'], ['NV', 'Nevada'],
    ['NH', 'New Hampshire'], ['NJ', 'New Jersey'], ['NM', 'New Mexico'], ['NY', 'New York'],
    ['NC', 'North Carolina'], ['ND', 'North Dakota'], ['OH', 'Ohio'], ['OK', 'Oklahoma'],
    ['OR', 'Oregon'], ['PA', 'Pennsylvania'], ['RI', 'Rhode Island'], ['SC', 'South Carolina'],
    ['SD', 'South Dakota'], ['TN', 'Tennessee'], ['TX', 'Texas'], ['UT', 'Utah'],
    ['VT', 'Vermont'], ['VA', 'Virginia'], ['WA', 'Washington'], ['WV', 'West Virginia'],
    ['WI', 'Wisconsin'], ['WY', 'Wyoming'],
  ];
  for (const [code, name] of STATES) group('state', [code, name]);
  group('state', ['DC', 'District of Columbia', 'Washington DC', 'Washington D.C.']);

  // No two-letter codes for countries: "CA" must mean California, never Canada.
  group('country', ['United States', 'United States of America', 'US', 'USA', 'U.S.', 'U.S.A.', 'America']);
  group('country', ['United Kingdom', 'UK', 'U.K.', 'Great Britain', 'GB']);
  group('country', ['Canada']);
  group('country', ['Mexico']);

  group('yn', [
    'Yes', 'Y', 'True',
    'Yes I am a veteran', 'I am a veteran', 'Veteran', 'Protected veteran', 'I am a protected veteran',
    'I identify as one or more of the classifications of protected veteran',
    'Yes I have a disability', 'I have a disability',
    'Yes I have a disability or have had one in the past',
  ]);
  group('yn', [
    'No', 'N', 'False', 'Nope',
    'Not a veteran', 'I am not a veteran', 'Not a protected veteran', 'I am not a protected veteran',
    'No I do not have a disability', 'I do not have a disability', "I don't have a disability",
    'No I do not have a disability and have not had one in the past',
  ]);

  group('gender', ['Male', 'Man', 'M']);
  group('gender', ['Female', 'Woman', 'F']);
  group('gender', ['Non-binary', 'Nonbinary', 'Non binary', 'Genderqueer', 'Gender non-conforming']);

  group('race', ['Asian']);
  group('race', ['Black or African American', 'Black', 'African American']);
  group('race', ['White', 'Caucasian']);
  group('race', ['Two or more races', 'Multiracial', 'Mixed race']);
  group('race', ['American Indian or Alaska Native', 'Native American']);
  group('race', ['Native Hawaiian or Other Pacific Islander', 'Pacific Islander']);
  group('hisp', ['Hispanic or Latino', 'Hispanic', 'Latino', 'Latina', 'Latinx', 'Hispanic Latino or Spanish origin']);
  group('hisp', ['Not Hispanic or Latino', 'Non-Hispanic', 'Not Hispanic']);

  // Competes with every family.
  group('*', [
    'Decline', 'Decline to self identify', 'I decline to self identify', 'Decline to answer',
    'Decline to state', 'I do not wish to answer', "I don't wish to answer", 'I do not want to answer',
    "I don't want to answer", 'I prefer not to answer', 'Prefer not to answer', 'Prefer not to say',
    'I prefer not to say', 'Prefer not to disclose', 'I choose not to disclose', 'Choose not to disclose',
    'I do not wish to self identify', "I don't wish to self identify", 'I do not wish to disclose',
    'Rather not say', 'Not specified', 'Not disclosed',
  ]);

  const BY_PHRASE = new Map();
  for (const g of GROUPS) {
    for (const p of g.set) {
      if (!BY_PHRASE.has(p)) BY_PHRASE.set(p, []);
      BY_PHRASE.get(p).push(g);
    }
  }

  function groupsOf(v) { return BY_PHRASE.get(norm(v)) || []; }

  // Normalized phrases that mean the same as v, v itself first.
  function aliases(v) {
    const n = norm(v);
    if (!n) return [];
    const out = [n];
    for (const g of groupsOf(v)) for (const p of g.set) if (!out.includes(p)) out.push(p);
    return out;
  }

  // ---- Scoring ------------------------------------------------------------------------
  const PLACEHOLDER_RE = /^(please )?(select|choose|pick)( (one|an option|an? [a-z ]+))?$/;
  function isPlaceholder(raw) {
    const n = norm(raw);
    if (!n) return true;
    if (PLACEHOLDER_RE.test(n)) return true;
    return n === 'none selected';
  }

  const CODE_FIRST = /^\s*([a-z]{2})\s*[-\u2013\u2014:]\s*(.+?)\s*$/i;
  const CODE_LAST = /^\s*(.+?)\s*\(\s*([a-z]{2})\s*\)\s*$/i;

  // Best [score, matched alias length] of a candidate text against a set of phrases.
  function tier(raw, set) {
    const cn = norm(raw);
    if (!cn) return [0, 0];
    if (set.has(cn)) return [100, cn.length];

    const m = CODE_FIRST.exec(raw) || CODE_LAST.exec(raw);
    if (m) {
      const parts = CODE_FIRST.test(raw) ? [m[1], m[2]] : [m[2], m[1]];
      if (set.has(norm(parts[0])) && set.has(norm(parts[1]))) return [90, norm(parts[0]).length + norm(parts[1]).length];
    }

    const padded = ' ' + cn + ' ';
    let best = [0, 0];
    for (const a of set) {
      let s = 0;
      if (a.length >= 2 && padded.includes(' ' + a + ' ')) s = 85;
      else if (a.length >= 4 && cn.startsWith(a)) s = 70;
      if (s > best[0] || (s === best[0] && s > 0 && a.length > best[1])) best = [s, a.length];
    }
    return best;
  }

  function beats(a, b) { return a[0] > b[0] || (a[0] === b[0] && a[1] > b[1]); }

  function scoreText(raw, target) {
    if (isPlaceholder(raw)) return 0;
    const mine = new Set(aliases(target));
    if (!mine.size) return 0;
    const own = tier(raw, mine);
    if (own[0] === 0) return 0;

    const targetGroups = groupsOf(target);
    const families = new Set(targetGroups.map((g) => g.family));
    for (const g of GROUPS) {
      if (targetGroups.includes(g)) continue;
      if (!(g.family === '*' || families.has('*') || families.has(g.family))) continue;
      if (!beats(own, tier(raw, g.set))) return 0;
    }
    return own[0];
  }

  // Score an option (its visible label and its value attribute) against the profile value.
  function scoreOption(label, value, target) {
    let best = 0;
    for (const t of [label, value]) {
      if (t == null || t === '') continue;
      const s = scoreText(t, target);
      if (s > best) best = s;
    }
    return best;
  }

  const api = { scoreOption, aliases, norm, isPlaceholder };
  root.AF = root.AF || {};
  Object.assign(root.AF, api);
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(globalThis);
