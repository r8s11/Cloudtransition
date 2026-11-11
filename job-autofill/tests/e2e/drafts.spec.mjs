import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { launch, openPopup, runAutofill } from './harness.mjs';

const YELLOW = 'rgb(202, 138, 4)';
const GREEN = 'rgb(22, 163, 74)';
async function setup(fn, { ai = false, fallback = true } = {}) {
  const h = await launch({ fallback });
  try {
    if (ai) h.helper.setKey('anthropic', 'fixture-provider-key');
    await h.pair();
    await h.page.goto(h.fixtureUrl('greenhouse-questions.html'));
    const { popup } = await openPopup(h.page);
    if (ai) expect(await popup.evaluate(() => chrome.runtime.sendMessage({ type: 'SAVE_CONFIG', patch: { provider: 'anthropic', models: { anthropic: 'fake-anthropic-a' } } }))).not.toHaveProperty('error');
    expect(await popup.evaluate(() => chrome.runtime.sendMessage({ type: 'SAVE_PROFILE', manual: { country: 'United States', workAuthorization: 'Yes', needsSponsorship: 'No', gender: 'Male' } }))).not.toHaveProperty('error');
    await popup.close();
    await fn(h);
  } finally { await h.close(); }
}
const draftRequests = async (h) => (await h.provider.requests()).filter(r => r.path === '/v1/messages');
async function reviewed(page, reason = 'AI draft — review before submitting') {
  await expect(page.locator('#answer')).toHaveAttribute('title', `AutoFill: ${reason}`);
  expect(await page.locator('#answer').evaluate(e => getComputedStyle(e).borderTopColor)).toBe(YELLOW);
}

test('U11: AI draft fills the question, stays yellow, and sends no profile values', async () => {
  await setup(async h => {
    const result = await runAutofill(h.page);
    expect(result.counts.ai_drafts).toBe(1);
    expect(result.counts.ai_calls).toBe(1);
    const value = await h.page.locator('#answer').inputValue();
    expect(value.length).toBeGreaterThan(0);
    expect(value.length).toBeLessThanOrEqual(500);
    await reviewed(h.page);
    await expect(h.page.locator('#autofill-hud')).toContainText('1 to review');
    const requests = await draftRequests(h);
    expect(requests).toHaveLength(1);
    const payload = JSON.stringify(requests[0].body);
    expect(payload).toContain('Why do you want to work at Northwind?');
    expect(payload).toContain('Northwind');
    expect(payload).toContain('resume');
    for (const secret of ['jordan.avery@example.test', '555-010-0199', 'workAuthorization', 'needsSponsorship', 'gender']) expect(payload).not.toContain(secret);
    expect(JSON.stringify(await h.worker.evaluate(() => chrome.storage.local.get(null)))).not.toContain('fixture-provider-key');
  }, { ai: true });
});

test('U19: trusted-input fallback attaches and detaches; disabled fallback leaves yellow', async () => {
  await setup(async h => {
    await h.page.goto(h.fixtureUrl('generic-trusted.html'));
    await h.worker.evaluate(() => {
      globalThis.__dbg = { attach: 0, detach: 0 };
      for (const k of ['attach', 'detach']) {
        const original = chrome.debugger[k].bind(chrome.debugger);
        chrome.debugger[k] = (...args) => { globalThis.__dbg[k]++; return original(...args); };
      }
    });
    await runAutofill(h.page);
    await expect(h.page.locator('#email')).toHaveValue('jordan.avery@example.test');
    expect(await h.page.locator('#email').evaluate(e => getComputedStyle(e).borderTopColor)).toBe(GREEN);
    expect(await h.worker.evaluate(() => globalThis.__dbg)).toEqual({ attach: 1, detach: 1 });
    await h.worker.evaluate(() => chrome.storage.local.set({ prefs: { fallback: false } }));
    await h.page.reload();
    await runAutofill(h.page);
    await expect(h.page.locator('#email')).toHaveValue('');
    await expect(h.page.locator('#email')).toHaveAttribute('title', "AutoFill: Couldn't set this field");
    expect(await h.worker.evaluate(() => globalThis.__dbg)).toEqual({ attach: 1, detach: 1 });
  });
});

test('F12: sign-in and account pages stay untouched', async () => {
  await setup(async h => {
    for (const name of ['workday-signin.html', 'indeed-signin.html']) {
      await h.page.goto(h.fixtureUrl(name));
      await runAutofill(h.page, { submit: true });
      await expect(h.page.locator('input[type=email]')).toHaveValue('');
      expect(await h.page.locator('body').getAttribute('data-clicks')).toBe('0');
      await expect(h.page.locator('#autofill-hud')).toContainText("Sign in first — AutoFill doesn't sign in or create accounts");
    }
    for (const form of [
      '<label>Email<input type="email"></label><input type="password" hidden><button>Continue</button>',
      '<label>Email<input type="email"></label><button>Create Account</button>',
    ]) {
      await h.page.goto(h.fixtureUrl('indeed-signin.html'));
      await h.page.evaluate(form => { document.body.innerHTML = `<form>${form}</form>`; }, form);
      await runAutofill(h.page, { submit: true });
      await expect(h.page.locator('input[type=email]')).toHaveValue('');
      await expect(h.page.locator('#autofill-hud')).toContainText("Sign in first — AutoFill doesn't sign in or create accounts");
    }
  });
});

test('F13: resume fills only resume slots and a single unlabeled upload needs review', async () => {
  await setup(async h => {
    await h.page.goto(h.fixtureUrl('file-slots.html'));
    await runAutofill(h.page);
    expect(await h.page.locator('input').evaluateAll(els => els.map(e => e.files.length))).toEqual([1, 0, 0, 0]);
    await h.page.goto(h.fixtureUrl('file-unlabeled.html'));
    await runAutofill(h.page);
    expect(await h.page.locator('input').evaluate(e => e.files.length)).toBe(1);
    await expect(h.page.locator('input')).toHaveAttribute('title', "AutoFill: Unlabeled upload — check it's the resume box");
  });
});

test('U20: offline fills cached profile and resume but leaves AI unavailable', async () => {
  await setup(async h => {
    await h.helper.stop();
    const result = await runAutofill(h.page);
    expect(result.text).toContain('Helper offline — profile from last sync');
    await expect(h.page.locator('#first_name')).toHaveValue('Jordan');
    expect(await h.page.locator('#resume').evaluate(e => e.files.length)).toBe(1);
    await expect(h.page.locator('#answer')).toHaveValue('');
    await reviewed(h.page, 'Helper offline — AI drafts unavailable');
  }, { ai: true });
});

test('F19: missing resume remains yellow while other fields fill', async () => {
  await setup(async h => {
    const { popup } = await openPopup(h.page);
    await popup.evaluate(() => chrome.runtime.sendMessage({ type: 'SAVE_CONFIG', patch: { resume_pdf: '/missing/resume.pdf' } }));
    await popup.close();
    await runAutofill(h.page);
    await expect(h.page.locator('#first_name')).toHaveValue('Jordan');
    expect(await h.page.locator('#resume').evaluate(e => e.files.length)).toBe(0);
    await expect(h.page.locator('#resume')).toHaveAttribute('title', 'AutoFill: Resume file not found — pick it in Profile');
    const p = await openPopup(h.page);
    await p.popup.getByRole('tab', { name: 'Profile' }).click();
    await expect(p.popup.locator('body')).toContainText('Resume file not found — pick it in Profile');
    await p.popup.close();
  });
});

for (const [mode, reason] of [['401', 'key rejected'], ['429', 'rate limited'], ['500', 'provider error 500'], ['slow', 'timed out'], ['malformed', 'unreadable reply']]) {
  test(`F9: provider ${mode} surfaces errors and retries instead of caching`, async () => {
    test.setTimeout(120_000);
    await setup(async h => {
      await h.provider.setMode(mode);
      for (let i = 0; i < 2; i++) {
        if (i) await h.page.reload();
        const result = await runAutofill(h.page, { timeout: 50_000 });
        expect(result.counts.ai_calls).toBe(1);
        await expect(h.page.locator('#answer')).toHaveValue('');
        await reviewed(h.page, `AI error: ${reason}`);
      }
      expect(await draftRequests(h)).toHaveLength(2);
    }, { ai: true });
  });
}

test('F20: hidden injection cannot change system rules and the echo remains yellow', async () => {
  await setup(async h => {
    await h.provider.setMode('echo');
    await runAutofill(h.page, { submit: true });
    const [request] = await draftRequests(h);
    expect(request.body.system).toContain('resume');
    expect(request.body.system).not.toContain('Northwind');
    expect(JSON.stringify(request.body)).not.toContain('Ignore previous instructions');
    const user = JSON.parse(request.body.messages[0].content);
    expect(user.company).toBe('Northwind');
    expect(user.question).toBe('Why do you want to work at Northwind?');
    expect(user.page_title).toBe('Support at Northwind');
    expect(user.job_heading).toBe('Support Specialist');
    await reviewed(h.page);
    expect(await h.page.locator('body').getAttribute('data-submit-clicks')).toBe('0');
  }, { ai: true });
});

test('U25: cached answer uses no second provider call and reports zero calls', async () => {
  await setup(async h => {
    await runAutofill(h.page);
    const first = await h.page.locator('#answer').inputValue();
    await h.page.reload();
    const second = await runAutofill(h.page);
    await expect(h.page.locator('#answer')).toHaveValue(first);
    await expect.poll(() => {
      try {
        const lines = readFileSync(path.join(h.helper.home, 'runs.jsonl'), 'utf8').trim().split('\n');
        return JSON.parse(lines.at(-1)).ai_calls;
      } catch (_) { return null; }
    }).toBe(0);
    expect(await draftRequests(h)).toHaveLength(1);
    expect(second.counts.ai_calls).toBe(0);
  }, { ai: true });
});

test('6c: rejected token blocks a run instead of using stale cache', async () => {
  await setup(async h => {
    const { popup, tabId } = await openPopup(h.page);
    await popup.evaluate(() => chrome.storage.local.set({ token: 'rejected-token' }));
    const result = await popup.evaluate(tabId => chrome.runtime.sendMessage({ type: 'RUN', tabId }), tabId);
    expect(result.error).toContain('Not paired');
    await expect(h.page.locator('#first_name')).toHaveValue('');
    await popup.close();
  });
});

test('6c: question types normalize unlimited length and exclude search and promo controls', async () => {
  await setup(async h => {
    await fetch(`http://127.0.0.1:${h.provider.port}/__mode`, {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ mode: 'ok', reply: '12' }),
    });
    await h.page.evaluate(() => {
      document.querySelector('form').innerHTML = '<label>How many projects?<input id="number" type="number"></label><label>Describe your projects<textarea id="text"></textarea></label><label>Which project count?<select id="select"><option value="">Choose</option><option value="twelve">12</option><option>Other</option></select></label><label>Search<input id="search"></label><label>Promo code<input id="promo"></label>';
    });
    const result = await runAutofill(h.page);
    expect(result.counts.ai_drafts).toBe(3);
    await expect(h.page.locator('#number')).toHaveValue('12');
    await expect(h.page.locator('#text')).toHaveValue('12');
    await expect(h.page.locator('#select')).toHaveValue('twelve');
    await expect(h.page.locator('#search')).toHaveValue('');
    await expect(h.page.locator('#promo')).toHaveValue('');
    const requests = await draftRequests(h);
    expect(requests).toHaveLength(3);
    for (const request of requests) {
      const user = JSON.parse(request.body.messages[0].content);
      expect(user.max_length || 0).toBe(0);
    }
  }, { ai: true });
});

test('6c: daily AI cap stays an empty yellow error without another provider call', async () => {
  await setup(async h => {
    const { popup } = await openPopup(h.page);
    await popup.evaluate(() => chrome.runtime.sendMessage({ type: 'SAVE_CONFIG', patch: { daily_cap: 0 } }));
    await popup.close();
    await runAutofill(h.page);
    await expect(h.page.locator('#answer')).toHaveValue('');
    await reviewed(h.page, 'Daily AI limit reached (0)');
    expect(await draftRequests(h)).toHaveLength(0);
  }, { ai: true });
});

test('6c: AI off leaves required questions empty without contacting provider', async () => {
  await setup(async h => {
    await runAutofill(h.page);
    await expect(h.page.locator('#answer')).toHaveValue('');
    await expect(h.page.locator('#answer')).toHaveAttribute('title', 'AutoFill: Required field still needs input');
    expect(await draftRequests(h)).toHaveLength(0);
  });
});

test('6c: review external sign-in heading blocks an email-only form', async () => {
  await setup(async h => {
    await h.page.evaluate(() => {
      document.body.innerHTML = '<h1>Sign in</h1><form><label>Email<input type="email" id="login-email"></label><button>Continue</button></form>';
      document.body.dataset.clicks = '0';
      document.querySelector('button').onclick = e => { e.preventDefault(); document.body.dataset.clicks = String(+document.body.dataset.clicks + 1); };
    });
    await runAutofill(h.page, { submit: true });
    await expect(h.page.locator('#login-email')).toHaveValue('');
    await expect(h.page.locator('#autofill-hud')).toContainText("Sign in first — AutoFill doesn't sign in or create accounts");
    expect(await h.page.locator('body').getAttribute('data-clicks')).toBe('0');
  });
});

test('6c: review header sign-in links do not block an application form', async () => {
  await setup(async h => {
    await h.page.evaluate(() => {
      document.body.innerHTML = '<form><header><a role="button" href="/login">Sign in</a></header><h1>Apply for Support Specialist</h1><label>First Name<input id="first_name"></label><button>Submit application</button></form>';
      document.body.dataset.clicks = '0';
      document.querySelector('a').onclick = e => { e.preventDefault(); document.body.dataset.clicks = String(+document.body.dataset.clicks + 1); };
    });
    await runAutofill(h.page);
    await expect(h.page.locator('#first_name')).toHaveValue('Jordan');
    expect(await h.page.locator('body').getAttribute('data-clicks')).toBe('0');
  });
});

test('6c: review enclosing form context excludes non-application AI questions', async () => {
  await setup(async h => {
    await h.page.evaluate(() => {
      document.body.innerHTML = '<form aria-label="Search"><label>Keywords<input id="q0"></label></form>'
        + '<form name="newsletter"><label>Topics<input id="q1"></label></form>'
        + '<form action="/login"><label>Account identifier<input id="q2"></label></form>'
        + '<form action="/promo"><label>Offer identifier<input id="q3"></label></form>'
        + '<form role="search"><label>Terms<input id="q4"></label></form>';
    });
    await runAutofill(h.page);
    expect(await draftRequests(h)).toHaveLength(0);
    expect(await h.page.locator('input').evaluateAll(els => els.map(e => e.value))).toEqual(['', '', '', '', '']);
  }, { ai: true });
});

test('6c: review nonempty placeholder values still request a select draft', async () => {
  await setup(async h => {
    await fetch(`http://127.0.0.1:${h.provider.port}/__mode`, {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ mode: 'ok', reply: 'Internal referral' }),
    });
    await h.page.evaluate(() => {
      document.querySelector('form').innerHTML = '<label>How did you learn about this position?<select id="answer" required><option value="-1">Select</option><option value="referral">Internal referral</option><option value="board">Job board</option></select></label>';
    });
    const result = await runAutofill(h.page);
    await expect(h.page.locator('#answer')).toHaveValue('referral');
    await reviewed(h.page);
    expect(result.counts.ai_drafts).toBe(1);
    const [request] = await draftRequests(h);
    expect(JSON.parse(request.body.messages[0].content).options).toEqual(['Internal referral', 'Job board']);
  }, { ai: true });
});

test('6c: review an independent login form does not block application filling', async () => {
  await setup(async h => {
    await h.page.evaluate(() => {
      document.body.innerHTML = '<header><form aria-label="Sign in"><label>Email<input id="login-email" type="email"></label><label>Password<input type="password"></label><button>Sign in</button></form></header><main><h1>Apply for Support Specialist</h1><form><label>First Name<input id="first_name"></label><button>Submit application</button></form></main>';
    });
    await runAutofill(h.page);
    await expect(h.page.locator('#first_name')).toHaveValue('Jordan');
    await expect(h.page.locator('#login-email')).toHaveValue('');
    await expect(h.page.locator('input[type=password]')).toHaveValue('');
  });
});

test('6c: sign-in form inside header is not filled', async () => {
  await setup(async h => {
    for (const container of ['header', 'nav']) {
      for (const [heading, action] of [['Sign in', 'Sign in'], ['Sign in', 'Continue'], ['', 'Sign in']]) {
        await h.page.goto(h.fixtureUrl('greenhouse-questions.html'));
        await h.page.evaluate(({ container, heading, action }) => {
          document.body.innerHTML = `<${container}><form>${heading ? `<h2>${heading}</h2>` : ''}<label>Email<input id="login-email" type="email"></label><button>${action}</button></form></${container}><main><h1>Apply for Support Specialist</h1><form><label>First Name<input id="first_name"></label><label>Email<input id="application-email" type="email"></label><button>Submit application</button></form></main>`;
          document.body.dataset.clicks = '0';
          document.querySelectorAll('button').forEach(button => {
            button.onclick = e => { e.preventDefault(); document.body.dataset.clicks = String(+document.body.dataset.clicks + 1); };
          });
        }, { container, heading, action });
        await runAutofill(h.page);
        await expect(h.page.locator('#login-email')).toHaveValue('');
        await expect(h.page.locator('#first_name')).toHaveValue('Jordan');
        await expect(h.page.locator('#application-email')).toHaveValue('jordan.avery@example.test');
        expect(await h.page.locator('body').getAttribute('data-clicks')).toBe('0');
      }
    }
  });
});
