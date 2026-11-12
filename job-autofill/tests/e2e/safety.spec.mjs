import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { launch, openPopup, runAutofill } from './harness.mjs';

const logs = h => { try { return readFileSync(path.join(h.helper.home, 'runs.jsonl'), 'utf8').trim().split('\n').map(JSON.parse); } catch { return []; } };
async function setup(fn, ai = false) {
  const h = await launch();
  try {
    if (ai) h.helper.setKey('anthropic', 'fixture-key');
    await h.pair();
    await h.page.goto(h.fixtureUrl('greenhouse.html'));
    const { popup } = await openPopup(h.page);
    await popup.evaluate(ai => chrome.runtime.sendMessage({ type: 'SAVE_PROFILE', manual: { country: 'United States', workAuthorization: 'Yes', needsSponsorship: 'No', gender: 'Male' } }), ai);
    if (ai) await popup.evaluate(() => chrome.runtime.sendMessage({ type: 'SAVE_CONFIG', patch: { provider: 'anthropic', models: { anthropic: 'fake-anthropic-a' } } }));
    await popup.close();
    await fn(h);
  } finally { await h.close(); }
}
async function stopped(h, reason, code) {
  const result = await runAutofill(h.page, { submit: true });
  expect(result.status).toBe('stopped');
  await expect(h.page.locator('#autofill-hud')).toContainText(`Stopped: ${reason}`);
  expect(await h.page.locator('body').getAttribute('data-submit-clicks')).toBe('0');
  if (code) await expect.poll(() => logs(h).at(-1)?.outcome).toBe(`stopped:${code}`);
}
test('F1: CAPTCHA in an embedded frame blocks all submit variants', async () => {
  await setup(async h => {
    for (const [name, label] of [['recaptcha', 'reCAPTCHA'], ['hcaptcha', 'hCaptcha'], ['turnstile', 'Turnstile'], ['arkose', 'Arkose']]) {
      await h.page.goto(h.fixtureUrl(`greenhouse-${name}.html`));
      await stopped(h, `${label} detected — finish and submit yourself`, 'captcha');
      await expect(h.page.locator('#first_name')).toHaveValue('Jordan');
    }
  });
});
test('F2: yellow field blocks submit', async () => { await setup(async h => {
  await h.page.goto(h.fixtureUrl('generic.html'));
  await stopped(h, '1 field to review', 'review');
}); });
test('F4: unanswered required sponsorship blocks submit without guessing', async () => { await setup(async h => {
  const { popup } = await openPopup(h.page);
  await popup.evaluate(() => chrome.runtime.sendMessage({ type: 'SAVE_PROFILE', manual: { needsSponsorship: '' } }));
  await popup.close();
  await stopped(h, '1 required field empty', 'required');
  await expect(h.page.locator('#question_4')).toHaveValue('');
  await expect(h.page.locator('#question_4')).toHaveAttribute('title', 'AutoFill: Required field still needs input');
}); });
test('F6: unconfirmed submit clicks once and later runs never retry', async () => { await setup(async h => {
  await h.page.goto(h.fixtureUrl('greenhouse-noconfirm.html'));
  const result = await runAutofill(h.page, { submit: true });
  expect(result.status).toBe('submitted_unconfirmed');
  await expect(h.page.locator('#autofill-hud')).toContainText('Submitted · not confirmed — check the page before trying again');
  await expect.poll(() => logs(h).at(-1)?.outcome).toBe('submitted_unconfirmed');
  await runAutofill(h.page, { submit: true });
  await expect(h.page.locator('#autofill-hud')).toContainText('Already submitted from this tab');
  expect(await h.page.locator('body').getAttribute('data-submit-clicks')).toBe('1');
}); });
test('F6: second tab independent', async () => { await setup(async h => {
  await h.page.goto(h.fixtureUrl('greenhouse-noconfirm.html'));
  const second = await h.context.newPage();
  await second.goto(h.page.url());
  await runAutofill(h.page, { submit: true });
  await runAutofill(second, { submit: true });
  expect(await h.page.locator('body').getAttribute('data-submit-clicks')).toBe('1');
  expect(await second.locator('body').getAttribute('data-submit-clicks')).toBe('1');
}); });
test('U15: safe submit navigates once and confirms', async () => { await setup(async h => {
  await h.page.goto(h.fixtureUrl('greenhouse-submit.html'));
  const result = await runAutofill(h.page, { submit: true });
  expect(result.status).toBe('submitted_confirmed');
  await expect(h.page).toHaveURL(/confirmation.html/);
  await expect(h.page.locator('#autofill-hud')).toContainText('Submitted · confirmed');
  expect(await h.page.evaluate(() => sessionStorage.getItem('submitClicks'))).toBe('1');
  await expect.poll(() => logs(h).length).toBe(1);
  expect(logs(h)[0].outcome).toBe('submitted_confirmed');
}); });
test('U21: exactly one value-free record per filled and submitted run', async () => { await setup(async h => {
  await runAutofill(h.page);
  await h.page.goto(h.fixtureUrl('greenhouse-submit.html'));
  await runAutofill(h.page, { submit: true });
  await expect.poll(() => logs(h).length).toBe(2);
  for (const rec of logs(h)) {
    expect(Object.keys(rec).sort()).toEqual(['time', 'host', 'path', 'ats', 'green', 'yellow', 'ai_drafts', 'ai_calls', 'steps', 'outcome'].sort());
    for (const value of ['Jordan', 'Avery', 'jordan.avery@example.test', '555-010-0199']) expect(JSON.stringify(rec)).not.toContain(value);
  }
}); });

test('final: 1 inverted sponsorship and citizenship labels need review', async () => { await setup(async h => {
  await h.page.goto(h.fixtureUrl('greenhouse-submit.html'));
  await h.page.locator('label[for="question_4"]').evaluate(el => { el.firstChild.textContent = 'Do you NOT require sponsorship? '; });
  await h.page.locator('#candidate-location').evaluate(el => {
    const field = document.createElement('div');
    field.innerHTML = '<label for="country">Country of citizenship</label><input id="country" name="country" type="text">';
    el.after(field);
  });
  const result = await runAutofill(h.page, { submit: true });
  expect(result.status).toBe('stopped');
  await expect(h.page.locator('#question_4')).toHaveValue('');
  await expect(h.page.locator('#country')).toHaveValue('');
  expect(await h.page.locator('body').getAttribute('data-submit-clicks')).toBe('0');
}); });

for (const [mutation, label] of [['inserted', 'required field inserted'], ['cleared', 'prefilled required field cleared'], ['file', 'required file input inserted']]) {
  test(`F4: ${label} after fill blocks submit`, async () => { await setup(async h => {
    const { popup, tabId } = await openPopup(h.page);
    await popup.close();
    await h.worker.evaluate(async ({ tabId, mutation }) => {
      await chrome.scripting.executeScript({
        target: { tabId }, args: [mutation],
        func: mutation => {
          if (mutation === 'cleared') document.querySelector('#first_name').value = 'Jordan';
          const fill = AF.fillPage;
          AF.fillPage = async (...args) => {
            const result = await fill(...args);
            if (mutation !== 'cleared') {
              const input = document.createElement('input');
              if (mutation === 'file') input.type = 'file';
              input.required = true;
              input.id = 'late-required';
              document.querySelector('form').append(input);
            } else document.querySelector('#first_name').value = '';
            return result;
          };
        },
      });
    }, { tabId, mutation });
    await stopped(h, '1 required field empty', 'required');
    await expect(h.page.locator(mutation === 'cleared' ? '#first_name' : '#late-required')).toHaveValue('');
  }); });
}

test('U15: confirmation rendered after navigation is detected', async () => { await setup(async h => {
  await h.context.route('**/receipt.html*', route => route.fulfill({
    contentType: 'text/html',
    body: '<!doctype html><html lang="en"><body><h1>Processing application</h1><script>setTimeout(() => document.querySelector("h1").textContent = "Thank you for applying", 700)</script></body></html>',
  }));
  await h.page.goto(h.fixtureUrl('greenhouse-submit.html'));
  await h.page.locator('form').evaluate(form => { form.action = 'receipt.html'; });
  const result = await runAutofill(h.page, { submit: true });
  expect(result.status).toBe('submitted_confirmed');
  await expect(h.page).toHaveURL(/receipt.html/);
  await expect(h.page.locator('#autofill-hud')).toContainText('Submitted · confirmed');
  await expect.poll(() => logs(h).length).toBe(1);
  expect(logs(h)[0].outcome).toBe('submitted_confirmed');
  expect(await h.page.evaluate(() => sessionStorage.getItem('submitClicks'))).toBe('1');
}); });
