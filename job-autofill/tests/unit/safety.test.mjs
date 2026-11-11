import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const context = { AF: {} };
if (fs.existsSync(new URL('../../extension/content/safety.js', import.meta.url))) vm.runInNewContext(fs.readFileSync(new URL('../../extension/content/safety.js', import.meta.url), 'utf8'), context);
const check = state => context.AF.safetyCheck(state);
test('safety: checks fail closed in documented order', () => {
  for (const [state, code] of [
    [{ captcha: 'reCAPTCHA', yellow: 1 }, 'captcha'],
    [{ yellow: 1, required: 1 }, 'review'],
    [{ required: 1, readback: 1 }, 'required'],
    [{ readback: 1 }, 'readback'],
    [{ button: false }, 'button'],
    [{ button: true, submitted: true }, 'duplicate'],
  ]) assert.equal(check(state).code, code);
  assert.equal(check({ button: true }).ok, true);
});
