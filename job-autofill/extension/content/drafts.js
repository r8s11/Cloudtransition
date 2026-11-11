// Rules applied to an AI draft after the helper returns it. Classic script: attaches to
// globalThis.AF and also exports through module.exports for the unit tests.
// A draft is only ever text or null; nothing here looks at how sure the model sounds.
(function (root) {
  'use strict';

  const OPTION_TYPES = new Set(['select', 'radio', 'combobox']);

  function stripFences(s) {
    let t = s.trim();
    t = /^```[^\n`]*\n/.test(t) ? t.replace(/^```[^\n`]*\n/, '') : t.replace(/^```/, '');
    t = t.replace(/\n?```$/, '');
    return t.trim();
  }

  // Cut to `max` UTF-16 units at a word boundary; a single word longer than max is hard-cut.
  function cut(text, max) {
    if (!(max > 0) || text.length <= max) return text;
    if (/\s/.test(text[max])) return text.slice(0, max).trimEnd();
    const head = text.slice(0, max);
    const space = head.search(/\s\S*$/);
    if (space > 0) return head.slice(0, space).trimEnd();
    const last = head.charCodeAt(max - 1);
    return last >= 0xd800 && last <= 0xdbff ? head.slice(0, max - 1) : head;
  }

  // Returns the string to put in the field, or null when nothing should be filled.
  function postProcess(text, { fieldType = 'text', maxLength = 0, options = [] } = {}) {
    if (typeof text !== 'string') return null;
    const t = stripFences(text);
    if (!t) return null;

    if (fieldType === 'number') {
      const m = t.match(/\d{1,3}(?:,\d{3})+|\d+/);
      return m ? m[0].replace(/,/g, '') : null;
    }
    if (OPTION_TYPES.has(fieldType)) {
      const list = Array.isArray(options) ? options.filter((o) => typeof o === 'string') : [];
      const exact = list.find((o) => o === t);
      if (exact !== undefined) return exact;
      const lower = t.toLowerCase();
      const loose = list.find((o) => o.trim().toLowerCase() === lower);
      return loose !== undefined ? loose : null;
    }
    const out = cut(t, maxLength);
    return out || null;
  }

  const api = { postProcess };
  root.AF = root.AF || {};
  Object.assign(root.AF, api);
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(globalThis);
