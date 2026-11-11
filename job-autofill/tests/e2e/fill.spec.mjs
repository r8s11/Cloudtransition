import { test, expect } from '@playwright/test';
import { launch, openPopup, runAutofill } from './harness.mjs';

const GREEN = 'rgb(22, 163, 74)';
const MANUAL = {
  street: '', zip: '', country: 'United States', workAuthorization: 'Yes', needsSponsorship: 'No',
  gender: 'Male', race: 'Asian', veteran: 'No', disability: 'No',
};

async function withExtension(fn) {
  const h = await launch();
  try {
    await h.pair();
    // Manual profile fields, saved through the same message the Profile tab sends.
    await h.page.goto(h.fixtureUrl('index.html'));
    const { popup } = await openPopup(h.page);
    const res = await popup.evaluate((manual) => chrome.runtime.sendMessage({ type: 'SAVE_PROFILE', manual }), MANUAL);
    expect(res.ok).toBe(true);
    await popup.close();
    await fn(h);
  } finally {
    await h.close();
  }
}

// Controls with the 2px green border.
const greenCount = (page) => page.evaluate((green) => [...document.querySelectorAll('input, select, textarea')]
  .filter((e) => { const s = getComputedStyle(e); return s.borderTopColor === green && s.borderTopWidth === '2px'; }).length, GREEN);

const borderOf = (loc) => loc.evaluate((e) => {
  const s = getComputedStyle(e);
  return { color: s.borderTopColor, width: s.borderTopWidth, inline: e.style.border };
});

const panel = (page) => page.locator('#autofill-hud .panel');

test('U4: fill a Greenhouse form', async () => {
  await withExtension(async (h) => {
    await h.page.goto(h.fixtureUrl('greenhouse.html'));
    const run = await runAutofill(h.page);
    const p = h.page;

    await expect(p.locator('#first_name')).toHaveValue('Jordan');
    await expect(p.locator('#last_name')).toHaveValue('Avery');
    await expect(p.locator('#email')).toHaveValue('jordan.avery@example.test');
    await expect(p.locator('#phone')).toHaveValue('555-010-0199');
    await expect(p.locator('#candidate-location')).toHaveValue('Springfield, IL');
    await expect(p.locator('#question_1')).toHaveValue('https://www.linkedin.com/in/jordan-avery-fixture');
    await expect(p.locator('#question_2')).toHaveValue('https://javery.example.test');
    const chosen = (sel) => p.locator(sel).evaluate((s) => s.options[s.selectedIndex].textContent);
    expect(await chosen('#question_3')).toBe('Yes');
    expect(await chosen('#question_4')).toBe('No');
    expect(await chosen('#gender')).toBe('Male');
    expect(await chosen('#race')).toBe('Asian');
    expect(await chosen('#veteran_status')).toBe('I am not a protected veteran');
    expect(await chosen('#disability_status')).toMatch(/^No, I do not have a disability/);

    // Resume goes in, cover letter stays empty.
    expect(await p.locator('#resume').evaluate((i) => [...i.files].map((f) => f.name))).toEqual(['resume.fixture.pdf']);
    expect(await p.locator('#cover_letter').evaluate((i) => i.files.length)).toBe(0);

    // 14 filled controls carry the 2px green border; the cover letter has none.
    expect(await greenCount(p)).toBe(14);
    expect((await borderOf(p.locator('#first_name'))).color).toBe(GREEN);
    expect((await borderOf(p.locator('#cover_letter'))).color).not.toBe(GREEN);
    await expect(p.locator('#first_name')).toHaveAttribute('title', 'AutoFill: From profile');

    expect(run.status).toBe('filled');
    expect(run.text).toContain('Filled 14 \u00b7 0 to review');
    await expect(panel(p)).toContainText('14 filled');
    await expect(panel(p)).toHaveAttribute('aria-live', 'polite');

    // No button was clicked.
    expect(await p.evaluate(() => document.body.dataset.submitClicks)).toBe('0');
  });
});

test('U5: fill a Lever form', async () => {
  await withExtension(async (h) => {
    await h.page.goto(h.fixtureUrl('lever.html'));
    const run = await runAutofill(h.page);
    const p = h.page;

    await expect(p.locator('input[name=name]')).toHaveValue('Jordan Avery');
    await expect(p.locator('input[name=email]')).toHaveValue('jordan.avery@example.test');
    await expect(p.locator('input[name=phone]')).toHaveValue('555-010-0199');
    await expect(p.locator('input[name="urls[LinkedIn]"]')).toHaveValue('https://www.linkedin.com/in/jordan-avery-fixture');
    await expect(p.locator('input[name="urls[GitHub]"]')).toHaveValue('https://github.com/javery-fixture');
    await expect(p.locator('input[name="urls[Portfolio]"]')).toHaveValue('https://javery.example.test');
    expect(await p.locator('input[name=resume]').evaluate((i) => [...i.files].map((f) => f.name))).toEqual(['resume.fixture.pdf']);

    // Current company is not in the profile; the optional textarea stays empty and unmarked.
    await expect(p.locator('input[name=org]')).toHaveValue('');
    await expect(p.locator('textarea[name=comments]')).toHaveValue('');
    const org = await borderOf(p.locator('input[name=org]'));
    const area = await borderOf(p.locator('textarea[name=comments]'));
    expect(org.inline).toBe('');
    expect(area.inline).toBe('');
    expect(area.color).not.toBe('rgb(202, 138, 4)');

    // Counts match the filled set: name, email, phone, three links, resume.
    expect(await greenCount(p)).toBe(7);
    expect(run.text).toContain('Filled 7 \u00b7 0 to review');
    await expect(panel(p)).toContainText('7 filled');
  });
});

test('U10: fill an unknown site by labels', async () => {
  await withExtension(async (h) => {
    await h.page.goto(h.fixtureUrl('generic.html'));
    const run = await runAutofill(h.page);
    const p = h.page;

    for (const [id, value] of [['#f1', 'Jordan'], ['#f2', 'jordan.avery@example.test'], ['#f3', '555-010-0199']]) {
      await expect(p.locator(id)).toHaveValue(value);
      expect((await borderOf(p.locator(id))).color).toBe(GREEN);
    }

    // The question-style label is yellow with its reason, or empty. Never green.
    const relocate = await borderOf(p.locator('#f4'));
    expect(relocate.color).not.toBe(GREEN);
    if ((await p.locator('#f4').inputValue()) !== '') {
      expect(relocate.color).toBe('rgb(202, 138, 4)');
      await expect(p.locator('#f4')).toHaveAttribute('title', 'AutoFill: Question-style label \u2014 check this answer');
    }
    expect(run.text).toContain('to review');
    expect(await p.evaluate(() => document.body.dataset.submitClicks)).toBe('0');
  });
});

test('F22: fields that already have a value are left alone', async () => {
  await withExtension(async (h) => {
    await h.page.goto(h.fixtureUrl('greenhouse.html'));
    await h.page.locator('#email').evaluate((e) => { e.value = 'someone@else.test'; });
    await h.page.locator('#first_name').fill('Morgan');
    const run = await runAutofill(h.page);
    const p = h.page;

    await expect(p.locator('#email')).toHaveValue('someone@else.test');
    await expect(p.locator('#first_name')).toHaveValue('Morgan');
    for (const id of ['#email', '#first_name']) {
      expect((await borderOf(p.locator(id))).inline).toBe('');
      expect((await borderOf(p.locator(id))).color).not.toBe(GREEN);
    }
    // The other fields fill normally and only they are counted.
    await expect(p.locator('#last_name')).toHaveValue('Avery');
    expect(await greenCount(p)).toBe(12);
    expect(run.text).toContain('Filled 12 \u00b7 0 to review');
  });
});
