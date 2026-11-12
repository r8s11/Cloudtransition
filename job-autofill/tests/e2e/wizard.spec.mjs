import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { launch, openPopup, runAutofill } from './harness.mjs';
const logs = h => { try { return readFileSync(path.join(h.helper.home, 'runs.jsonl'), 'utf8').trim().split('\n').map(JSON.parse); } catch { return []; } };
async function scenario(fn, name = 'workday/wizard.html') {
  const h = await launch();
  try { await h.pair(); await h.page.goto(h.fixtureUrl(name)); await fn(h, h.page); }
  finally { await h.close(); }
}
test('U16: safe wizard advances four steps and logs only final totals', async () => scenario(async (h, p) => {
  const r = await runAutofill(p, { submit: true });
  expect(r.status).toBe('submitted_confirmed');
  expect(r.step).toBe(4);
  expect(await p.locator('body').getAttribute('data-next-clicks')).toBe('3');
  expect(await p.locator('body').getAttribute('data-submit-clicks')).toBe('1');
  await expect.poll(() => logs(h).length).toBe(1);
  expect(logs(h)[0]).toMatchObject({ steps: 4, green: 3, outcome: 'submitted_confirmed' });
}));
test('final: 6 slow Next step is not treated as stalled', async () => scenario(async (h, p) => {
  const { popup, tabId } = await openPopup(p);
  await popup.close();
  await h.worker.evaluate(async tabId => chrome.scripting.executeScript({
    target: { tabId },
    func: () => {
      globalThis.__slowStep = { step: 1, stopped: '' };
      AF.wizard.onStep(({ step }) => { globalThis.__slowStep.step = step; });
      AF.wizard.start({ onStop: reason => { globalThis.__slowStep.stopped = reason; } });
      AF.wizard.advancing();
      setTimeout(() => {
        const heading = document.createElement('h1');
        heading.textContent = 'Delayed next step';
        document.querySelector('main').append(heading);
      }, 1500);
    },
  }), tabId);
  await p.waitForTimeout(3000);
  const result = await h.worker.evaluate(async tabId => {
    const [state] = await chrome.scripting.executeScript({ target: { tabId }, func: () => globalThis.__slowStep });
    return state.result;
  }, tabId);
  expect(result.step).toBe(2);
  expect(result.stopped).toBe('');
}));
test('F15: validation rerender stops after one Next', async () => scenario(async (h, p) => {
  const r = await runAutofill(p, { submit: true });
  expect(r.reason).toBe("page didn't advance");
  expect(await p.locator('body').getAttribute('data-next-clicks')).toBe('1');
  expect(logs(h).at(-1)?.outcome).toBe('stopped:no_advance');
}, 'workday-validation.html'));
test('F15: twelve-step wizard stops at ten', async () => scenario(async (h, p) => {
  const r = await runAutofill(p, { submit: true });
  expect(r.reason).toBe('10-step limit'); expect(r.step).toBe(10);
  expect(await p.locator('body').getAttribute('data-next-clicks')).toBe('9');
}, 'workday-twelve.html'));
test('U18: clear restores styles and Stop prevents next arrival filling', async () => scenario(async (h, p) => {
  const original = await p.locator('input').evaluate(e => { e.style.border='3px dotted red'; e.style.boxShadow='red 0px 0px 2px'; e.title='Original'; return [e.style.border,e.style.boxShadow,e.title]; });
  await runAutofill(p);
  await p.getByRole('button', { name: 'Clear borders', exact: true }).click();
  expect(await p.locator('input').evaluate(e => [e.style.border,e.style.boxShadow,e.title])).toEqual(original);
  await p.getByRole('button', { name: 'Stop', exact: true }).click();
  await expect(p.locator('#autofill-hud')).toContainText('Stopped');
  await p.getByRole('button', { name: 'Next', exact: true }).click();
  await p.waitForTimeout(1300); await expect(p.locator('input')).toHaveValue('');
  await expect.poll(() => logs(h).length).toBe(1);
  expect(logs(h)[0].steps).toBe(1);
}));
test('F16: stopped service worker wakes and keeps cumulative steps', async () => scenario(async (h, p) => {
  const r = await runAutofill(p);
  const cdp = await h.context.newCDPSession(p);
  await cdp.send('ServiceWorker.enable');
  await cdp.send('ServiceWorker.stopAllWorkers');
  await p.getByRole('button', { name: 'Next', exact: true }).click();
  await expect(p.locator('input')).toHaveValue('Avery');
  const { popup } = await openPopup(p);
  await expect.poll(() => popup.evaluate(async id => (await chrome.storage.session.get('runs')).runs[id].step, r.tabId)).toBe(2);
  const state = await popup.evaluate(async id => (await chrome.storage.session.get('runs')).runs[id], r.tabId);
  expect(state.step).toBe(2); expect(state.counts.green).toBe(2); expect(state.fingerprints).toHaveLength(2);
  expect(logs(h)).toHaveLength(0); await popup.close();
}));
test('U18: Stop cancels pending AI fill before writing response', async () => scenario(async (h, p) => {
  h.helper.setKey('anthropic', 'fixture-key');
  const {popup, tabId} = await openPopup(p);
  await popup.evaluate(() => chrome.runtime.sendMessage({type:'SAVE_CONFIG',patch:{provider:'anthropic',models:{anthropic:'fake-anthropic-a'}}}));
  await h.worker.evaluate(async tabId => chrome.scripting.executeScript({target:{tabId},func:()=> {
    const send=chrome.runtime.sendMessage.bind(chrome.runtime);
    chrome.runtime.sendMessage=async msg => msg.type==='DRAFT' ? (await AF.util.sleep(1200), {text:'Delayed draft',cached:false}) : send(msg);
  }}),tabId);
  await p.locator('main').evaluate(e=>e.innerHTML='<form aria-label="Application"><label>Why this role?<textarea></textarea></label></form>');
  await popup.getByRole('button',{name:'Autofill page',exact:true}).click();
  await p.getByRole('button',{name:'Stop',exact:true}).click();
  await p.waitForTimeout(1800); await expect(p.locator('textarea')).toHaveValue(''); await popup.close();
}));
test('F15: idle wizard ends after five minutes without a new step', async () => scenario(async (h,p)=>{
  const {popup,tabId}=await openPopup(p); await popup.close();
  await h.worker.evaluate(async tabId=>chrome.scripting.executeScript({target:{tabId},func:()=>{
    const original=setTimeout;
    globalThis.setTimeout=(cb,ms,...args)=>{
      if(ms===300000) globalThis.expireWizardIdle=cb;
      return original(cb,ms,...args);
    };
  }}),tabId);
  await runAutofill(p);
  await h.worker.evaluate(async tabId=>chrome.scripting.executeScript({target:{tabId},func:()=>globalThis.expireWizardIdle()}),tabId);
  await expect(p.locator('#autofill-hud')).toContainText('Stopped: 5-minute idle limit');
  await expect.poll(()=>logs(h).length).toBe(1);
}));
test('7b: queued old-document REPORT and LOG_RUN cannot revive reloaded run', async () => scenario(async(h,p)=>{
  const {popup,tabId}=await openPopup(p);
  await h.worker.evaluate(async tabId=>chrome.scripting.executeScript({target:{tabId},func:()=>{AF.fillPage=()=>new Promise(()=>{});}}),tabId);
  await popup.getByRole('button',{name:'Autofill page',exact:true}).click();
  await expect.poll(()=>popup.evaluate(async id=>(await chrome.storage.session.get('runs')).runs[id]?.runId,tabId)).toBeTruthy();
  const runId = await popup.evaluate(async id => (await chrome.storage.session.get('runs')).runs[id].runId, tabId);
  await h.worker.evaluate(()=>{globalThis.releaseQueue=null; runsQueue=new Promise(resolve=>globalThis.releaseQueue=resolve);});
  await h.worker.evaluate(async ({tabId,runId})=>chrome.scripting.executeScript({target:{tabId},args:[runId],func:runId=>{chrome.runtime.sendMessage({type:'REPORT',summary:{runId,status:'running',step:99}});chrome.runtime.sendMessage({type:'LOG_RUN',runId,status:'filled'});}}),{tabId,runId});
  await p.reload(); await h.worker.evaluate(()=>globalThis.releaseQueue());
  await expect(popup.getByRole('button',{name:'Autofill page',exact:true})).toBeEnabled();
  const state=await popup.evaluate(async id=>(await chrome.storage.session.get('runs')).runs[id],tabId);
  expect(state.status).toBe('stopped'); expect(state.step).not.toBe(99);
  await expect.poll(()=>logs(h).length).toBe(1); await popup.close();
}));
test('7b: SAFE_CLICK rechecks live page safety before clicking', async () => scenario(async (h, p) => {
  await h.worker.evaluate(() => {
    const send = chrome.tabs.sendMessage.bind(chrome.tabs);
    chrome.tabs.sendMessage = async (tabId, msg, opts) => {
      if (msg?.type === 'SAFE_CLICK') await chrome.scripting.executeScript({ target: { tabId }, func: () => document.querySelector('main').insertAdjacentHTML('afterbegin', '<div class="g-recaptcha"></div><label>Extra<input required></label>') });
      return send(tabId, msg, opts);
    };
  });
  const r = await runAutofill(p, { submit: true });
  expect(r.status).toBe('stopped');
  expect(await p.locator('body').getAttribute('data-next-clicks')).toBe('0');
}));
test('7b: Stop cancels queued real-input fill', async () => scenario(async (h, p) => {
  const { popup, tabId } = await openPopup(p);
  await p.locator('main').evaluate(e => { e.innerHTML = '<form aria-label="Application"><label>Email<input id="em" type="email"></label></form>'; e.querySelector('#em').addEventListener('input', ev => { if (!ev.isTrusted) ev.target.value = ''; }); });
  await h.worker.evaluate(tabId => debuggerQueues.set(tabId, new Promise(r => { globalThis.releaseDebugger = r; })), tabId);
  await popup.getByRole('button', { name: 'Autofill page', exact: true }).click();
  await p.waitForTimeout(800);
  await p.getByRole('button', { name: 'Stop', exact: true }).click();
  await expect(p.locator('#autofill-hud')).toContainText('Stopped');
  await h.worker.evaluate(() => globalThis.releaseDebugger());
  await p.waitForTimeout(1500); await expect(p.locator('#em')).toHaveValue(''); await popup.close();
}));
test('7b: passive run ends and logs at step 10', async () => scenario(async (h, p) => {
  await runAutofill(p);
  for (let i = 0; i < 9; i++) {
    await p.getByRole('button', { name: 'Next', exact: true }).click();
    await expect(p.locator('main input')).not.toHaveValue('');
  }
  await expect.poll(() => logs(h).length).toBe(1);
  expect(logs(h)[0]).toMatchObject({ steps: 10, outcome: 'stopped:limit' });
}, 'workday-twelve.html'));
test('7b: new run logs the active previous run', async () => scenario(async (h, p) => {
  await runAutofill(p);
  await runAutofill(p);
  await expect.poll(() => logs(h).length).toBe(1);
  expect(logs(h)[0].steps).toBe(1);
}));
test('7b: Stop during filling logs fields already filled', async () => scenario(async (h, p) => {
  h.helper.setKey('anthropic', 'fixture-key');
  const { popup, tabId } = await openPopup(p);
  await popup.evaluate(() => chrome.runtime.sendMessage({ type: 'SAVE_CONFIG', patch: { provider: 'anthropic', models: { anthropic: 'fake-anthropic-a' } } }));
  await h.worker.evaluate(async tabId => chrome.scripting.executeScript({ target: { tabId }, func: () => {
    const send = chrome.runtime.sendMessage.bind(chrome.runtime);
    chrome.runtime.sendMessage = async msg => msg.type === 'DRAFT' ? (await AF.util.sleep(1500), { text: 'Delayed draft', cached: false }) : send(msg);
  } }), tabId);
  await p.locator('main').evaluate(e => e.innerHTML = '<form aria-label="Application"><label>First name<input></label><label>Why this role?<textarea></textarea></label></form>');
  await popup.getByRole('button', { name: 'Autofill page', exact: true }).click();
  await expect(p.locator('main input')).toHaveValue('Jordan');
  await p.getByRole('button', { name: 'Stop', exact: true }).click();
  await expect.poll(() => logs(h).length).toBe(1);
  expect(logs(h)[0]).toMatchObject({ steps: 1, green: 1 }); await popup.close();
}));
