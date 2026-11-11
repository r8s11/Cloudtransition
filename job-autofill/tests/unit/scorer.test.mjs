import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { scoreOption, aliases } = require('../../extension/content/scorer.js');

// Pick the option the filler would choose: highest score, first on ties, 0 means none.
function pick(target, options) {
  let best = null;
  let bestScore = 0;
  for (const o of options) {
    const s = scoreOption(o, o, target);
    if (s > bestScore) { best = o; bestScore = s; }
  }
  return best;
}

test('F14: "Male" picks Male from [Female, Male] and Female scores 0', () => {
  assert.equal(pick('Male', ['Female', 'Male']), 'Male');
  assert.equal(scoreOption('Female', 'Female', 'Male'), 0);
  assert.equal(scoreOption('Male', 'Male', 'Male'), 100);
});

test('F14: "Female" picks Female and Male scores 0', () => {
  assert.equal(pick('Female', ['Male', 'Female']), 'Female');
  assert.equal(scoreOption('Male', 'Male', 'Female'), 0);
});

test('F14: "CA" picks California from [Africa, California, Canada]', () => {
  assert.equal(pick('CA', ['Africa', 'California', 'Canada']), 'California');
  assert.equal(scoreOption('Africa', 'Africa', 'CA'), 0);
  assert.equal(scoreOption('Canada', 'Canada', 'CA'), 0);
  assert.equal(scoreOption('California', 'California', 'CA'), 100);
});

test('F14: "No" picks No from [None of the above, No, North Carolina]', () => {
  assert.equal(pick('No', ['None of the above', 'No', 'North Carolina']), 'No');
  assert.equal(scoreOption('None of the above', 'None of the above', 'No'), 0);
  assert.equal(scoreOption('North Carolina', 'NC', 'No'), 0);
});

test('F14: "NC" picks North Carolina, not South Carolina', () => {
  assert.equal(pick('NC', ['South Carolina', 'North Carolina', 'North Dakota']), 'North Carolina');
});

test('F14: "Virginia" does not pick West Virginia; "Washington" does not pick DC', () => {
  assert.equal(pick('Virginia', ['West Virginia', 'Virginia']), 'Virginia');
  assert.equal(scoreOption('West Virginia', 'WV', 'Virginia'), 0);
  assert.equal(scoreOption('Washington, D.C.', 'DC', 'Washington'), 0);
  assert.equal(scoreOption('District of Columbia', 'DC', 'DC'), 100);
});

test('F14: score tiers 100 / 90 / 85 / 70 / 0', () => {
  assert.equal(scoreOption('California', '', 'California'), 100);
  assert.equal(scoreOption('ca', '', 'California'), 100);
  assert.equal(scoreOption('CA - California', '', 'CA'), 90);
  assert.equal(scoreOption('California (CA)', '', 'California'), 90);
  assert.equal(scoreOption('State of California', '', 'California'), 85);
  assert.equal(scoreOption('Californian residents', '', 'California'), 70);
  assert.equal(scoreOption('Oregon', '', 'California'), 0);
});

test('F14: the option value attribute can carry the match', () => {
  assert.equal(scoreOption('Golden State', 'CA', 'California'), 100);
  assert.equal(scoreOption('Golden State', 'ZZ', 'California'), 0);
});

test('F14: placeholders score 0', () => {
  for (const p of ['Select...', 'Select', '--', '- Select -', 'Choose', 'Please select', 'Select one', 'Select an option', '']) {
    assert.equal(scoreOption(p, p, 'California'), 0, `placeholder ${JSON.stringify(p)}`);
    assert.equal(scoreOption(p, p, 'No'), 0, `placeholder ${JSON.stringify(p)}`);
  }
});

test('F14: country aliases', () => {
  for (const o of ['United States', 'United States of America', 'USA', 'US', 'U.S.', 'U.S.A.']) {
    assert.equal(scoreOption(o, o, 'United States'), 100, o);
  }
  assert.equal(scoreOption('United States (US)', '', 'United States'), 90);
  assert.equal(scoreOption('Canada', '', 'United States'), 0);
  assert.equal(scoreOption('United Kingdom', '', 'United States'), 0);
});

test('F14: all 50 states and DC map between name and two-letter code', () => {
  const pairs = [
    ['AL', 'Alabama'], ['AK', 'Alaska'], ['AZ', 'Arizona'], ['AR', 'Arkansas'], ['CA', 'California'],
    ['CO', 'Colorado'], ['CT', 'Connecticut'], ['DE', 'Delaware'], ['FL', 'Florida'], ['GA', 'Georgia'],
    ['HI', 'Hawaii'], ['ID', 'Idaho'], ['IL', 'Illinois'], ['IN', 'Indiana'], ['IA', 'Iowa'],
    ['KS', 'Kansas'], ['KY', 'Kentucky'], ['LA', 'Louisiana'], ['ME', 'Maine'], ['MD', 'Maryland'],
    ['MA', 'Massachusetts'], ['MI', 'Michigan'], ['MN', 'Minnesota'], ['MS', 'Mississippi'], ['MO', 'Missouri'],
    ['MT', 'Montana'], ['NE', 'Nebraska'], ['NV', 'Nevada'], ['NH', 'New Hampshire'], ['NJ', 'New Jersey'],
    ['NM', 'New Mexico'], ['NY', 'New York'], ['NC', 'North Carolina'], ['ND', 'North Dakota'], ['OH', 'Ohio'],
    ['OK', 'Oklahoma'], ['OR', 'Oregon'], ['PA', 'Pennsylvania'], ['RI', 'Rhode Island'], ['SC', 'South Carolina'],
    ['SD', 'South Dakota'], ['TN', 'Tennessee'], ['TX', 'Texas'], ['UT', 'Utah'], ['VT', 'Vermont'],
    ['VA', 'Virginia'], ['WA', 'Washington'], ['WV', 'West Virginia'], ['WI', 'Wisconsin'], ['WY', 'Wyoming'],
    ['DC', 'District of Columbia'],
  ];
  assert.equal(pairs.length, 51);
  for (const [code, name] of pairs) {
    assert.equal(scoreOption(name, name, code), 100, `${code} -> ${name}`);
    assert.equal(scoreOption(code, code, name), 100, `${name} -> ${code}`);
    assert.ok(aliases(code).includes(code.toLowerCase()) && aliases(code).includes(name.toLowerCase()), code);
  }
});

test('F14: yes/no phrasings, including sentences and the opposite answer', () => {
  assert.equal(scoreOption('Yes, I am authorized to work', '', 'Yes'), 85);
  assert.equal(scoreOption('No, I will not require sponsorship', '', 'No'), 85);
  assert.equal(scoreOption('No', '', 'Yes'), 0);
  assert.equal(scoreOption('Yes', '', 'No'), 0);
  assert.equal(scoreOption('true', '', 'Yes'), 100);
});

test('F14: EEO gender, race, veteran, disability and decline phrasings', () => {
  assert.equal(scoreOption('Male (he/him)', '', 'Male'), 85);
  assert.equal(scoreOption('Woman', '', 'Female'), 100);
  assert.equal(pick('Decline', ['Male', 'Female', 'I do not wish to answer']), 'I do not wish to answer');
  assert.equal(pick('Decline', ['I decline to self identify', 'Yes', 'No']), 'I decline to self identify');
  assert.equal(scoreOption('Prefer not to say', '', 'Male'), 0);

  const vet = ['I identify as one or more of the classifications of protected veteran', 'I am not a protected veteran', "I don't wish to answer"];
  assert.equal(pick('Not a protected veteran', vet), 'I am not a protected veteran');
  assert.equal(pick('Protected veteran', vet), vet[0]);
  assert.equal(pick('No', vet), 'I am not a protected veteran');

  const dis = ['Yes, I have a disability, or have had one in the past', 'No, I do not have a disability and have not had one in the past', 'I do not want to answer'];
  assert.equal(pick('Yes', dis), dis[0]);
  assert.equal(pick('No', dis), dis[1]);
  assert.equal(pick('Decline', dis), dis[2]);

  const race = ['Hispanic or Latino', 'Asian (Not Hispanic or Latino)', 'Black or African American', 'White'];
  assert.equal(pick('Hispanic or Latino', race), 'Hispanic or Latino');
  assert.equal(pick('Asian', race), 'Asian (Not Hispanic or Latino)');
  assert.equal(pick('Black', race), 'Black or African American');
});

test('F14: empty target scores 0', () => {
  assert.equal(scoreOption('Male', 'Male', ''), 0);
  assert.equal(scoreOption('Male', 'Male', null), 0);
});
