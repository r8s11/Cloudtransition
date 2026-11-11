import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { matchField } = require('../../extension/content/matcher.js');

test('F14: label "Country (United States only)" does not match state', () => {
  const r = matchField({ label: 'Country (United States only)' });
  assert.notEqual(r.key, 'state');
  assert.equal(r.key, 'country');
});

test('F14: label "Email address" matches email, not address', () => {
  const r = matchField({ label: 'Email address' });
  assert.equal(r.key, 'email');
  assert.notEqual(r.key, 'address');
});

test('F14: a real street-address label still matches address; line 2 does not', () => {
  assert.equal(matchField({ label: 'Street address' }).key, 'address');
  assert.equal(matchField({ label: 'Address' }).key, 'address');
  assert.equal(matchField({ label: 'Address line 2' }).key, null);
});

test('F14: "State" and "State / Province" match state', () => {
  assert.equal(matchField({ label: 'State' }).key, 'state');
  assert.equal(matchField({ label: 'State / Province' }).key, 'state');
});

test('F14: specific keys win over generic ones', () => {
  assert.equal(matchField({ label: 'Website address' }).key, 'website');
  assert.equal(matchField({ label: 'LinkedIn profile URL' }).key, 'linkedin');
  assert.equal(matchField({ label: 'GitHub URL' }).key, 'github');
  assert.equal(matchField({ label: 'Will you now or in the future require visa sponsorship?' }).key, 'sponsorship');
  assert.equal(matchField({ label: 'Are you legally authorized to work in the United States?' }).key, 'workAuth');
  assert.equal(matchField({ label: 'Zip / Postal code' }).key, 'zip');
});

test('F14: name fields and EEO fields', () => {
  assert.equal(matchField({ label: 'First name' }).key, 'firstName');
  assert.equal(matchField({ label: 'Last Name' }).key, 'lastName');
  assert.equal(matchField({ label: 'Full name' }).key, 'fullName');
  assert.equal(matchField({ label: 'Name' }).key, 'fullName');
  assert.equal(matchField({ label: 'Company name' }).key, null);
  assert.equal(matchField({ label: 'Phone' }).key, 'phone');
  assert.equal(matchField({ label: 'Gender' }).key, 'gender');
  assert.equal(matchField({ label: 'Race / Ethnicity' }).key, 'race');
  assert.equal(matchField({ label: 'Veteran status' }).key, 'veteran');
  assert.equal(matchField({ label: 'Disability status' }).key, 'disability');
});

test('F14: autocomplete tokens, then name/id/placeholder/automationId when the label is empty', () => {
  assert.equal(matchField({ autocomplete: 'given-name' }).key, 'firstName');
  assert.equal(matchField({ autocomplete: 'section-x shipping postal-code' }).key, 'zip');
  assert.equal(matchField({ name: 'first_name' }).key, 'firstName');
  assert.equal(matchField({ id: 'lastName' }).key, 'lastName');
  assert.equal(matchField({ placeholder: 'you@example.com', name: 'email' }).key, 'email');
  assert.equal(matchField({ automationId: 'legalNameSection_firstName' }).key, 'firstName');
  assert.equal(matchField({ label: 'Mystery field' }).key, null);
});

test('U10: question-style labels are flagged, short naming labels are not', () => {
  const relocate = matchField({ label: 'Are you willing to relocate to this city?' });
  assert.equal(relocate.questionStyle, true);
  assert.equal(matchField({ label: 'First name' }).questionStyle, false);
  assert.equal(matchField({ label: 'Email' }).questionStyle, false);
  assert.equal(matchField({ label: 'Phone' }).questionStyle, false);
});

test('U10: question style is "?" or more than six words', () => {
  assert.equal(matchField({ label: 'Phone?' }).questionStyle, true);
  assert.equal(matchField({ label: 'One two three four five six' }).questionStyle, false);
  assert.equal(matchField({ label: 'One two three four five six seven' }).questionStyle, true);
  assert.equal(matchField({ name: 'email' }).questionStyle, false);
});
