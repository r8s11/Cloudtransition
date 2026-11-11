import { test, expect } from '@playwright/test';
import { ROOT, launch, openPopup, runAutofill } from './harness.mjs';
import path from 'node:path';
async function scenario(name, fn) {
 const h=await launch();try{await h.pair();await h.page.goto(h.fixtureUrl('index.html'));const {popup}=await openPopup(h.page);await popup.evaluate(()=>chrome.runtime.sendMessage({type:'SAVE_PROFILE',manual:{country:'United States',gender:'Male',workAuthorization:'Yes',needsSponsorship:'No'}}));await popup.close();await h.page.goto(h.fixtureUrl(name));await fn(h,h.page);}finally{await h.close()}
}
test('U6: Ashby portaled options, shadow field and sponsorship',async()=>scenario('ashby.html',async(h,p)=>{
 await runAutofill(p);await expect(p.locator('[name=_systemfield_name]')).toHaveValue('Jordan Avery');await expect(p.locator('[name=_systemfield_email]')).toHaveValue('jordan.avery@example.test');await expect(p.locator('#shadow input')).toHaveValue('555-010-0199');await expect(p.getByRole('combobox')).toHaveText('United States');await expect(p.getByRole('combobox')).toHaveAttribute('aria-expanded','false');await expect(p.getByRole('option')).toHaveCount(0);await expect(p.locator('[value=No]')).toBeChecked();await expect(p.locator('[value=Yes]')).not.toBeChecked();
}));
test('U7: Workday fills each manual step including drop-only resume',async()=>scenario('workday/index.html',async(h,p)=>{
 await runAutofill(p);await expect(p.locator('[data-automation-id=legalNameSection_firstName]')).toHaveValue('Jordan');await expect(p.locator('[data-automation-id=legalNameSection_lastName]')).toHaveValue('Avery');await expect(p.getByRole('combobox')).toHaveText('United States');expect(await p.locator('body').getAttribute('data-next-clicks')).toBe('0');await p.getByRole('button',{name:'Next',exact:true}).click();await expect(p.locator('[data-automation-id=file-upload-drop-zone]')).toHaveText('resume.fixture.pdf',{timeout:3000});await p.getByRole('button',{name:'Next',exact:true}).click();await expect(p.locator('select')).toHaveValue('Male',{timeout:3000});await expect(p.locator('#autofill-hud .panel')).toContainText('Step 3');expect(await p.locator('body').getAttribute('data-next-clicks')).toBe('2');expect(await p.locator('body').getAttribute('data-submit-clicks')).toBe('0');
}));
test('U8: cross-origin iCIMS frame totals survive either report order',async()=>scenario('icims-host.html',async(h,p)=>{
 await p.goto(h.fixtureUrl('icims-host.html')+'?form='+encodeURIComponent(h.fixtureUrl('icims-form.html','B')));const frame=p.frameLocator('iframe');await expect(frame.locator('input')).toHaveCount(2);const run=await runAutofill(p);await expect(p.locator('#host-name')).toHaveValue('Jordan');await expect(frame.locator('input').nth(0)).toHaveValue('Avery');await expect(frame.locator('input').nth(1)).toHaveValue('jordan.avery@example.test');await expect(p.locator('#autofill-hud .panel')).toContainText('3 filled');await expect(p.locator('#autofill-hud')).toHaveCount(1);await expect(frame.locator('#autofill-hud')).toHaveCount(0);const {popup}=await openPopup(p);try{await expect(popup.locator('#run-card-line')).toHaveText('Filled 3 · 0 to review');const frames=await popup.evaluate(async(id)=>Object.keys((await chrome.storage.session.get('runs')).runs[id].frames),run.tabId);expect(frames).toHaveLength(2);}finally{await popup.close()}
}));
test('U9: Indeed fills manual arrivals and review preserves answers',async()=>scenario('indeed/index.html',async(h,p)=>{
 await runAutofill(p);await expect(p.locator('[name=fullName]')).toHaveValue('Jordan Avery');await expect(p.locator('[name=email]')).toHaveValue('jordan.avery@example.test');expect(await p.locator('body').getAttribute('data-continue-clicks')).toBe('0');await p.getByRole('button',{name:'Continue',exact:true}).click();await expect.poll(()=>p.locator('input[type=file]').evaluate(e=>e.files[0]?.name),{timeout:3000}).toBe('resume.fixture.pdf');await p.getByRole('button',{name:'Continue',exact:true}).click();await expect(p.locator('[name=workAuthorization][value=Yes]')).toBeChecked({timeout:3000});await expect(p.locator('[name=needsSponsorship][value=No]')).toBeChecked();await p.getByRole('button',{name:'Continue',exact:true}).click();await expect(p.locator('#review')).toContainText('Jordan Avery');await expect(p.locator('#review')).toContainText('resume.fixture.pdf');await expect(p.locator('#review')).toContainText('"workAuthorization":"Yes"');await expect(p.locator('#review')).toContainText('"needsSponsorship":"No"');expect(await p.locator('body').getAttribute('data-continue-clicks')).toBe('3');expect(await p.locator('body').getAttribute('data-submit-clicks')).toBe('0');
}));

async function loadWidgetCore(page, html) {
  await page.setContent(html);
  for (const name of ['util', 'scorer', 'matcher', 'adapters', 'fill']) {
    await page.addScriptTag({ path: path.join(ROOT, 'extension', 'content', `${name}.js`) });
  }
}

test('6b: Workday drops respect resume labels and reject other document slots', async ({ page }) => {
  await loadWidgetCore(page, `
    <div data-automation-id="file-upload-drop-zone" aria-label="Resume"></div>
    <div data-automation-id="file-upload-drop-zone" aria-label="CV"></div>
    <div data-automation-id="file-upload-drop-zone" aria-label="Cover letter"></div>
    <div data-automation-id="file-upload-drop-zone" aria-label="Resume photo"></div>
    <div data-automation-id="file-upload-drop-zone" aria-label="Transcript"></div>
    <style>[data-automation-id] { width: 200px; height: 40px }</style>
  `);
  const result = await page.evaluate(async () => {
    const resume = { name: 'resume.fixture.pdf', b64: btoa('%PDF fixture') };
    const adapter = AF.adapterFor('example.myworkdayjobs.com');
    const dropped = [];
    const accept = (el) => el.addEventListener('drop', (event) => {
      dropped.push(el.getAttribute('aria-label') || 'unlabeled');
      el.textContent = event.dataTransfer.files[0].name;
    });
    document.querySelectorAll('[data-automation-id]').forEach(accept);
    const first = await AF.fillPage(document, {}, resume, { adapter });
    document.body.innerHTML = '<div data-automation-id="file-upload-drop-zone" style="width:200px;height:40px"></div>';
    accept(document.querySelector('div'));
    const second = await AF.fillPage(document, {}, resume, { adapter });
    return {
      dropped,
      first: first.items.map(({ level, filled }) => ({ level, filled })),
      second: second.items.map(({ level, filled, reason }) => ({ level, filled, reason })),
    };
  });
  expect(result.dropped).toEqual(['Resume', 'CV', 'unlabeled']);
  expect(result.first).toEqual([{ level: 'green', filled: true }, { level: 'green', filled: true }]);
  expect(result.second).toEqual([{
    level: 'yellow', filled: true, reason: "Unlabeled upload — check it's the resume box",
  }]);
});

test('6b: combobox read-back grades the displayed option instead of the clicked option', async ({ page }) => {
  await loadWidgetCore(page, `
    <button role="combobox" aria-label="City" aria-expanded="false" aria-controls="cities">Select</button>
  `);
  const results = await page.evaluate(async () => {
    const button = document.querySelector('button');
    let selected = '';
    button.onclick = () => {
      const list = document.createElement('div');
      list.id = 'cities';
      const option = document.createElement('div');
      option.setAttribute('role', 'option');
      option.textContent = 'York';
      option.onclick = () => {
        button.textContent = selected;
        button.setAttribute('aria-expanded', 'false');
        list.remove();
      };
      list.append(option);
      document.body.append(list);
      button.setAttribute('aria-expanded', 'true');
    };
    const results = [];
    for (const displayed of ['Yorkshire', 'Paris', 'York']) {
      selected = displayed;
      button.textContent = 'Select';
      const result = await AF.fillPage(document, { city: 'York' }, null, { adapter: AF.adapterFor('jobs.ashbyhq.com') });
      results.push(result.items.map(({ level, filled, reason }) => ({ level, filled, reason })));
    }
    return results;
  });
  expect(results).toEqual([
    [{ level: 'yellow', filled: true, reason: 'Close match — check this option' }],
    [{ level: 'yellow', filled: false, reason: "Couldn't set this field" }],
    [{ level: 'green', filled: true, reason: 'From profile' }],
  ]);
});

test('6b: editable comboboxes select a real option and count once', async ({ page }) => {
  await loadWidgetCore(page, `
    <input role="combobox" aria-label="Country" aria-controls="countries" aria-expanded="false">
    <input aria-haspopup="listbox" aria-label="City" aria-controls="cities" aria-expanded="false">
  `);
  const result = await page.evaluate(async () => {
    let opens = 0;
    let clicks = 0;
    for (const input of document.querySelectorAll('input')) {
      input.onclick = () => {
        opens += 1;
        input.setAttribute('aria-expanded', 'true');
        const list = document.createElement('div');
        list.id = input.getAttribute('aria-controls');
        const option = document.createElement('div');
        option.setAttribute('role', 'option');
        option.textContent = list.id === 'countries' ? 'United States' : 'Springfield';
        option.onclick = () => {
          clicks += 1;
          input.value = option.textContent;
          input.setAttribute('aria-expanded', 'false');
          list.remove();
        };
        list.append(option);
        document.body.append(list);
      };
    }
    const result = await AF.fillPage(document, { country: 'United States', city: 'Springfield' }, null, {
      adapter: AF.adapterFor('jobs.ashbyhq.com'),
    });
    return {
      opens, clicks, fields: result.fields,
      items: result.items.map(({ kind, level, filled }) => ({ kind, level, filled })),
      values: [...document.querySelectorAll('input')].map((el) => el.value),
    };
  });
  expect(result).toEqual({
    opens: 2, clicks: 2, fields: 2,
    items: [{ kind: 'combo', level: 'green', filled: true }, { kind: 'combo', level: 'green', filled: true }],
    values: ['United States', 'Springfield'],
  });
});
