import { test, expect } from '@playwright/test';
import { ROOT, launch, openPopup, runAutofill } from './harness.mjs';
import path from 'node:path';

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

async function loadCore(page, html) {
  await page.setContent(html);
  for (const name of ['util', 'scorer', 'matcher', 'adapters', 'fill', 'hud']) {
    await page.addScriptTag({ path: path.join(ROOT, 'extension', 'content', `${name}.js`) });
  }
}

test('6a: select read-back rejects a different option at the same index', async ({ page }) => {
  await loadCore(page, '<label>State<select><option value="">Select</option><option value="IL">Illinois</option></select></label>');
  const result = await page.evaluate(async () => {
    const select = document.querySelector('select');
    select.addEventListener('change', () => setTimeout(() => {
      select.options[1].value = 'NY';
      select.options[1].textContent = 'New York';
    }, 30), { once: true });
    const { items } = await AF.fillPage(document, { state: 'IL' }, null);
    return { value: select.value, level: items[0].level, filled: items[0].filled, reason: items[0].reason };
  });
  expect(result).toEqual({ value: 'NY', level: 'yellow', filled: false, reason: "Couldn't set this field" });
});

test('6a: clearing highlights restores mixed border longhands and priorities', async ({ page }) => {
  await loadCore(page, '<input title="Original hint" style="border-top: 3px dashed red !important; border-right-width: 5px; border-bottom-color: blue !important; border-left-style: dotted; box-shadow: 1px 2px 3px black !important">');
  const result = await page.evaluate(() => {
    const input = document.querySelector('input');
    const properties = ['top', 'right', 'bottom', 'left'].flatMap((side) =>
      ['width', 'style', 'color'].map((part) => `border-${side}-${part}`)).concat('box-shadow');
    const snapshot = () => ({
      styles: properties.map((p) => [p, input.style.getPropertyValue(p), input.style.getPropertyPriority(p)]),
      title: input.getAttribute('title'),
    });
    const before = snapshot();
    AF.highlight(input, 'green', 'From profile');
    AF.highlight(input, 'yellow', 'Review');
    AF.clearHighlights();
    return { before, after: snapshot() };
  });
  expect(result.after).toEqual(result.before);
});

test('6a: unresolved required radio groups and checkboxes need review', async ({ page }) => {
  await loadCore(page, `<form>
    <fieldset><legend>Choose a shift</legend><label><input id="day" type="radio" name="shift" value="day">Day</label>
    <label><input id="night" type="radio" name="shift" value="night" required>Night</label></fieldset>
    <label><input id="consent" type="checkbox" required>Consent</label>
    <label><input id="checked" type="checkbox" required checked>Accepted</label>
    <label><input id="optional" type="checkbox">Optional</label>
    <label><input id="disabled" type="checkbox" required disabled>Disabled</label>
    <fieldset><legend>Chosen shift</legend><label><input type="radio" name="chosen" required>Day</label>
    <label><input type="radio" name="chosen" checked>Night</label></fieldset>
  </form>`);
  const items = await page.evaluate(async () => {
    const { items } = await AF.fillPage(document, {}, null);
    for (const item of items) AF.highlight(item.el, item.level, item.reason);
    return items.map(({ el, level, reason, filled }) => ({ id: el.id, level, reason, filled }));
  });
  expect(items).toEqual([
    { id: 'day', level: 'yellow', reason: 'Required field still needs input', filled: false },
    { id: 'consent', level: 'yellow', reason: 'Required field still needs input', filled: false },
  ]);
  await expect(page.locator('#day')).toHaveAttribute('title', 'AutoFill: Required field still needs input');
  await expect(page.locator('#consent')).toHaveAttribute('title', 'AutoFill: Required field still needs input');
});

test('6a: whole-list reinjection preserves one HUD and highlight restoration', async () => {
  await withExtension(async (h) => {
    await h.page.goto(h.fixtureUrl('greenhouse.html'));
    await h.page.locator('#first_name').evaluate((e) => {
      e.style.borderTop = '3px dashed red';
      e.title = 'Original hint';
    });
    await runAutofill(h.page);
    const { popup, tabId } = await openPopup(h.page);
    await popup.close();
    await h.worker.evaluate(async (tabId) => {
      await chrome.scripting.executeScript({
        target: { tabId },
        files: chrome.runtime.getManifest().content_scripts[0].js,
      });
    }, tabId);
    const run = await runAutofill(h.page);
    expect(run.text).toContain('Filled 14 · 0 to review');
    await expect(h.page.locator('#autofill-hud')).toHaveCount(1);
    await panel(h.page).getByRole('button', { name: 'Clear borders' }).click();
    await expect(h.page.locator('#first_name')).toHaveAttribute('title', 'Original hint');
    expect(await h.page.locator('#first_name').evaluate((e) => e.style.borderTop)).toBe('3px dashed red');
  });
});

test('6a: REPORT and popup count fills separately from empty required reviews', async () => {
  await withExtension(async (h) => {
    await h.page.goto(h.fixtureUrl('generic.html'));
    await h.page.evaluate(() => {
      document.body.innerHTML = '<label>First name<input id="name"></label><label>Explain your motivation<textarea required></textarea></label>';
    });
    const run = await runAutofill(h.page);
    expect(run.counts.filled).toBe(1);
    expect(run.counts.yellow).toBe(1);
    expect(run.text).toContain('Filled 1 · 1 to review');
    await expect(panel(h.page)).toContainText('1 filled');
    const { popup } = await openPopup(h.page);
    try {
      await expect(popup.locator('#run-card-line')).toHaveText('Filled 1 · 1 to review');
      await expect(popup.locator('#run-msg')).toHaveText('Filled 1 · 1 to review');
    } finally {
      await popup.close();
    }
  });
});
