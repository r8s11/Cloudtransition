import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { postProcess } = require('../../extension/content/drafts.js');

const OPTIONS = ['0-1', '2-4', '5+'];

test('U12: select reply "5+" is filled as "5+"', () => {
  assert.equal(postProcess('5+', { fieldType: 'select', options: OPTIONS }), '5+');
});

test('U12: select reply "five or more" is not filled', () => {
  assert.equal(postProcess('five or more', { fieldType: 'select', options: OPTIONS }), null);
});

test('U12: select reply must be one of the options, whatever the case or padding', () => {
  assert.equal(postProcess('  2-4\n', { fieldType: 'select', options: OPTIONS }), '2-4');
  assert.equal(postProcess('Yes', { fieldType: 'select', options: ['yes', 'no'] }), 'yes');
  assert.equal(postProcess('5+ years', { fieldType: 'select', options: OPTIONS }), null);
  assert.equal(postProcess('5+', { fieldType: 'select', options: [] }), null);
  assert.equal(postProcess('5+', { fieldType: 'select' }), null);
});

test('U12: number reply "About 7 years" is filled as "7"', () => {
  assert.equal(postProcess('About 7 years', { fieldType: 'number' }), '7');
  assert.equal(postProcess('12', { fieldType: 'number' }), '12');
  assert.equal(postProcess('Around 1,500 people', { fieldType: 'number' }), '1500');
});

test('U12: text reply of 90 characters with max 40 is cut at a word boundary, no trailing space', () => {
  const reply = 'alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima mike november oscar';
  assert.ok(reply.length >= 90);
  const out = postProcess(reply.slice(0, 90), { fieldType: 'text', maxLength: 40 });
  assert.ok(out.length <= 40, `length ${out.length}`);
  assert.equal(out, 'alpha bravo charlie delta echo foxtrot');
  assert.equal(out, out.trimEnd());
});

test('U12: a reply that already fits is returned whole, a max of 0 or none means no limit', () => {
  assert.equal(postProcess('Short answer.', { fieldType: 'textarea', maxLength: 40 }), 'Short answer.');
  const long = 'word '.repeat(100).trim();
  assert.equal(postProcess(long, { fieldType: 'textarea' }), long);
  assert.equal(postProcess(long, { fieldType: 'textarea', maxLength: 0 }), long);
});

test('U12: a cut that lands exactly on a word end keeps the whole word', () => {
  assert.equal(postProcess('alpha bravo charlie', { fieldType: 'text', maxLength: 11 }), 'alpha bravo');
  assert.equal(postProcess('alpha bravo charlie', { fieldType: 'text', maxLength: 12 }), 'alpha bravo');
});

test('F11: a reply longer than max with no spaces is hard-cut at max', () => {
  const out = postProcess('x'.repeat(120), { fieldType: 'text', maxLength: 50 });
  assert.equal(out, 'x'.repeat(50));
});

test('F11: a hard cut never splits a surrogate pair', () => {
  const out = postProcess('\u{1F600}'.repeat(10), { fieldType: 'text', maxLength: 5 });
  assert.equal(out, '\u{1F600}'.repeat(2));
});

test('F11: an empty or blank reply means not filled', () => {
  for (const reply of ['', '   ', '\n\n', null, undefined, '```\n```']) {
    for (const fieldType of ['text', 'textarea', 'number', 'select']) {
      assert.equal(postProcess(reply, { fieldType, maxLength: 100, options: OPTIONS }), null,
        `${JSON.stringify(reply)} as ${fieldType}`);
    }
  }
});

test('F11: "none" for a number field means not filled', () => {
  assert.equal(postProcess('none', { fieldType: 'number' }), null);
  assert.equal(postProcess('N/A', { fieldType: 'number' }), null);
});

test('F11: markdown fences around the text are stripped', () => {
  assert.equal(postProcess('```\nHello there.\n```', { fieldType: 'text' }), 'Hello there.');
  assert.equal(postProcess('```text\nHello there.\n```\n', { fieldType: 'textarea' }), 'Hello there.');
  assert.equal(postProcess('```Hello there.```', { fieldType: 'text' }), 'Hello there.');
  assert.equal(postProcess('```\n7\n```', { fieldType: 'number' }), '7');
  assert.equal(postProcess('```\n5+\n```', { fieldType: 'select', options: OPTIONS }), '5+');
});
