// /jev command checks against REAL `omp --mode rpc` processes with local fake providers only
// (Jev, Anthropic-style and Codex-style helpers are 127.0.0.1 servers). No paid call can occur.
// Covers jev-command U2, U3, U4, F1, F2, F3, R1, R2.
//   TMPDIR=<dir with space> bun tools/jev-routing/runtime-matrix.mjs [evidence-output-file]
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, readFile, rm } from 'node:fs/promises';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { startServer, startOmp, sse, textOfContent } from './harness.mjs';

const exec = promisify(execFile);
const outFile = process.argv[2];
const lines = [];
const note = (...a) => { const s = a.join(' '); lines.push(s); console.log(s); };
const json = (res, body, status = 200) => { res.writeHead(status, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(body)); };
const work = await mkdtemp(join(process.env.JEV_TMP || tmpdir(), 'jev-matrix-'));
const KEY = 'KEY-CANARY-5b21e8d0';
const MANDATORY = 'MANDATORY-POLICY: parent session rules stay binding for every helper.';

const TASKS = [
 { text: 'What is the capital of Australia?', kind: 'non-coding', diff: 'easy', model: 'anthropic/haiku-fixture' },
 { text: 'Rename the variable x to count in: let x = 0; x++;', kind: 'coding', diff: 'easy', model: 'openai-codex/codex-mini-fixture' },
 { text: 'Summarise the pros and cons of remote work for a small team.', kind: 'non-coding', diff: 'medium', model: 'anthropic/sonnet-fixture' },
 { text: 'Fix the off-by-one error in this pagination helper that skips the last page.', kind: 'coding', diff: 'medium', model: 'openai-codex/codex-fixture' },
 { text: 'Design a multi-region architecture for a payment ledger with strict consistency.', kind: 'coding', diff: 'hard', model: 'anthropic/opus-fixture' },
 { text: 'Diagnose why customer churn rose after the pricing change given conflicting survey data.', kind: 'non-coding', diff: 'hard', model: 'anthropic/opus-fixture' },
];
const PROVIDERS = { jevmain: ['main'], anthropic: ['haiku-fixture', 'sonnet-fixture', 'opus-fixture', 'broken-fixture'], 'openai-codex': ['codex-mini-fixture', 'codex-fixture'] };

// Fake Jev + fake provider endpoints. `state` is flipped by scenarios.
function world(state) {
 return startServer(async ({ event, data, res }) => {
  if (event.path === '/classify') {
   const mode = state.classify || 'pick';
   if (mode === '401') { json(res, {}, 401); return true; }
   if (mode === '500') { json(res, {}, 500); return true; }
   if (mode === 'drop') { res.destroy(); return true; }
   if (mode === 'hang') return true;
   const answers = {};
   for (const [id, q] of Object.entries(data.questions)) {
    const names = Object.keys(q.criteria);
    const task = data.state?.task || '';
    const known = TASKS.find(t => task.includes(t.text));
    let choice = '__none__';
    if (names.includes('easy')) choice = known?.diff || 'medium';
    else if (state.forceModel && names.includes(state.forceModel)) choice = state.forceModel;
    else if (known && names.includes(known.model)) choice = known.model;
    else if (names.includes('anthropic/sonnet-fixture')) choice = 'anthropic/sonnet-fixture';
    state.decisions.push({ seq: event.seq, kind: names.includes('easy') ? 'difficulty' : 'model', options: names, choice });
    answers[id] = { type: 'choice', choice };
   }
   json(res, { model: 'jev-1.14.0', answers, usage: { input_tokens: 100 } });
   return true;
  }
  const users = data.messages.filter(m => m.role === 'user');
  const lastUser = textOfContent(users.at(-1)?.content);
  const system = data.messages.filter(m => m.role === 'system' || m.role === 'developer').map(m => textOfContent(m.content)).join('\n');
  event.system = system;
  if (data.model === 'main') {
   if (system.includes('MANDATORY') && data.messages.at(-1)?.role === 'user') { /* main model gets a plain answer */ }
   sse(res, [{ role: 'assistant', content: 'MAIN ANSWER' }]);
   return true;
  }
  if (data.model === 'broken-fixture') { json(res, { error: { message: 'invalid api key' } }, 401); return true; }
  if (state.toolOnce && data.messages.every(m => m.role !== 'tool')) {
   sse(res, [{ role: 'assistant', tool_calls: [{ index: 0, id: 'tc-1', type: 'function', function: { name: 'read', arguments: JSON.stringify({ path: state.toolPath }) } }] }], 'tool_calls');
   return true;
  }
  if (state.helperDelayMs) await new Promise(r => setTimeout(r, state.helperDelayMs));
  const toolMsg = data.messages.find(m => m.role === 'tool');
  // 400: the read tool prefixes a [path#tag] header, and a long TMPDIR pushed the content past the old 100-char echo.
  if (toolMsg) { sse(res, [{ role: 'assistant', content: `TOOL-RESULT-SEEN: ${textOfContent(toolMsg.content).replace(/\n/g, ' ').slice(0, 400)}` }]); return true; }
  const task = TASKS.filter(t => lastUser.includes(t.text)).sort((a, b) => lastUser.lastIndexOf(b.text) - lastUser.lastIndexOf(a.text))[0]?.text || lastUser.split('\n\n').at(-1);
  sse(res, [{ role: 'assistant', content: `ANSWER[${data.model}] ${task.slice(0, 40)}` }]);
  return true;
 });
}
const classifyEvents = s => s.events.filter(e => e.path === '/classify');
const hostHints = s => s.events.filter(e => e.path !== '/classify' && e.data.messages?.some(m => m.role === 'user' && textOfContent(m.content).startsWith('Compress into one routing hint')));
const helperEvents = s => s.events.filter(e => e.path !== '/classify' && e.model !== 'main' && !hostHints(s).includes(e));
const mainEvents = s => s.events.filter(e => e.model === 'main');
const readLog = async p => { try { return (await readFile(p, 'utf8')).trim().split('\n').filter(Boolean).map(l => JSON.parse(l)); } catch { return []; } };
const shown = om => om.messages().filter(m => m.role === 'custom').map(m => m.text);
const newState = extra => ({ classify: 'pick', decisions: [], ...extra });
async function enable(om, cmd = '/jev on') {
 const n = om.messages().length;
 await om.prompt(cmd);
 await om.waitFor(() => om.messages().slice(n).some(m => /^Jev (on|skills)\./.test(m.text) || /remains off/.test(m.text)), 'enable result');
}
const providerOf = n => n.split('/')[0];

try {
 // ---- M1: U2 + U4 (both families) -----------------------------------------------------
 note('## Scenario 1 (U2, U4): six tasks, both families available');
 {
  const log = join(work, 'm1.jsonl');
  const state = newState();
  const srv = await world(state);
  const om = await startOmp({ config: { origin: srv.origin, providers: PROVIDERS, key: KEY, log }, extraArgs: ['--model', 'jevmain/main'] });
  await enable(om);
  note('enable prompts:', om.uiRequests.filter(u => ['input', 'confirm'].includes(u.method)).map(u => `${u.method}: ${u.title}`).join(' | '));
  note('status after enable:', shown(om).find(t => /^Jev on/.test(t)));
  for (const [i, t] of TASKS.entries()) {
   const seq0 = srv.events.length;
   const msg0 = shown(om).length;
   const expectedReply = `ANSWER[${t.model.split('/')[1]}] ${t.text.slice(0, 40)}`;
   await om.prompt(t.text);
   try {
    await om.waitFor(() => shown(om).some(x => x.startsWith(expectedReply.slice(0, 30)) && x.includes(t.text.slice(0, 40))) || shown(om).some(x => /failed or input was blocked/.test(x)), `reply to task ${i + 1}`, 30000);
    if (!shown(om).some(x => x.startsWith(expectedReply.slice(0, 30)) && x.includes(t.text.slice(0, 40)))) throw Error('Helper failed: ' + JSON.stringify((await readLog(log)).slice(-4)) + '; decisions: ' + JSON.stringify(state.decisions.slice(-2)) + '; provider models: ' + helperEvents(srv).map(e => e.model).join(',') + '; stderr: ' + om.stderr());
   } catch (error) { await om.stop(); srv.close(); throw error; }
   const ev = srv.events.slice(seq0);
   const cls = ev.filter(e => e.path === '/classify'), hlp = helperEvents(srv).filter(e => ev.includes(e));
   const diffReq = cls[0], modelReq = cls[1];
   assert.equal(cls.length, 2, 'difficulty then model Choice');
   assert.ok(Object.keys(Object.values(diffReq.data.questions)[0].criteria).includes('easy'));
   assert.ok(cls[1].seq > cls[0].seq && hlp[0].seq > cls[1].seq, 'Jev answered before the helper was called');
   const helperUserMsgs = hlp.flatMap(e => e.data.messages.filter(m => m.role === 'user').map(m => textOfContent(m.content)));
   const carriesTask = hlp.filter(e => e.data.messages.some(m => m.role === 'user' && textOfContent(m.content).endsWith(t.text)));
   assert.equal(hlp.length, 1, 'exactly one helper request');
   assert.equal(carriesTask.length, 1);
   assert.equal(hlp[0].model, t.model.split('/')[1]);
   const pickLine = shown(om).slice(msg0).filter(x => x.includes(`${t.diff} → ${t.model}`)).length;
   note(`${i + 1}. [${t.kind}, ${t.diff}] Jev requests ${cls.length} (difficulty then helper model) -> ${t.model}; helper requests ${hlp.length}; family ${providerOf(t.model) === 'anthropic' ? 'Claude' : 'Codex'}; pick line shown ${pickLine === 1}`);
   void helperUserMsgs;
  }
  const records = await readLog(log);
  const picked = records.filter(r => r.outcome === 'picked'), ok = records.filter(r => r.outcome === 'success');
  note('log entries per task (outcome sequence):', JSON.stringify([...new Set(records.map(r => r.id))].map(id => records.filter(r => r.id === id).map(r => r.outcome).join('>'))));
  note('log: picked', picked.map(r => `${r.difficulty}/${r.model}`).join(', '));
  assert.equal(picked.length, 6); assert.equal(ok.length, 6);
  assert.deepEqual(picked.map(r => [r.difficulty, r.model]), TASKS.map(t => [t.diff, t.model]));
  const raw = await readFile(log, 'utf8');
  note('log contains any task text:', TASKS.some(t => raw.includes(t.text.slice(0, 15))), '| key:', raw.includes(KEY), '| log fields:', JSON.stringify([...new Set(records.flatMap(r => Object.keys(r)))].sort()));
  assert.ok(!TASKS.some(t => raw.includes(t.text.slice(0, 15))) && !raw.includes(KEY));
  // U4: what the model Choice actually offered.
  const modelReq = state.decisions.find(d => d.kind === 'model');
  const by = {};
  for (const n of modelReq.options) if (n !== '__none__') by[providerOf(n)] = (by[providerOf(n)] || 0) + 1;
  note('U4 candidates offered to Jev (model Choice), by provider:', JSON.stringify(by));
  note('U4 fixture models present:', ['anthropic/haiku-fixture', 'anthropic/sonnet-fixture', 'anthropic/opus-fixture', 'openai-codex/codex-mini-fixture', 'openai-codex/codex-fixture'].every(n => modelReq.options.includes(n)), '| non-chat/other-company providers offered:', Object.keys(by).filter(p => !['anthropic', 'openai', 'openai-codex'].includes(p)).length);
  assert.ok(Object.keys(by).every(p => ['anthropic', 'openai', 'openai-codex'].includes(p)));
  assert.ok(by.anthropic >= 4 && by['openai-codex'] >= 2);
  note('Result: PASS');
  await om.stop(); srv.close();
 }

 // ---- M2: U4 single-family catalogues ----------------------------------------------------
 for (const [label, providers, missing, present] of [
  ['Anthropic only', { jevmain: ['main'], anthropic: ['haiku-fixture', 'sonnet-fixture', 'opus-fixture'] }, 'OpenAI', 'anthropic'],
  ['OpenAI/Codex only', { jevmain: ['main'], 'openai-codex': ['codex-mini-fixture', 'codex-fixture'] }, 'Anthropic', 'openai-codex'],
 ]) {
  note(`\n## Scenario 2 (U4): ${label} catalogue`);
  const state = newState({});
  const srv = await world(state);
  const om = await startOmp({ config: { origin: srv.origin, providers, key: KEY, log: join(work, 'm2.jsonl') }, extraArgs: ['--model', 'jevmain/main'] });
  await enable(om);
  const report = shown(om).filter(t => /helper models unavailable/.test(t));
  note('reported to user:', JSON.stringify(report));
  assert.equal(report.length, 1); assert.ok(report[0].startsWith(missing));
  const task = present === 'anthropic' ? TASKS[0] : TASKS[1];
  await om.prompt(task.text);
  await om.waitFor(() => shown(om).some(x => x.startsWith('ANSWER[')), 'helper answer');
  const d = state.decisions.find(x => x.kind === 'model');
  const by = {}; for (const n of d.options) if (n !== '__none__') by[providerOf(n)] = (by[providerOf(n)] || 0) + 1;
  note('model Choice offered, by provider:', JSON.stringify(by), '| unavailable family offered:', Object.keys(by).some(p => missing === 'OpenAI' ? p.startsWith('openai') : p === 'anthropic'));
  assert.ok(!Object.keys(by).some(p => missing === 'OpenAI' ? p.startsWith('openai') : p === 'anthropic'));
  const used = helperEvents(srv).map(e => e.model);
  note('helper model actually called:', used.join(','), '(no substitution from the missing family)');
  note('Result: PASS');
  await om.stop(); srv.close();
 }

 // ---- M3: U3 queued/busy ---------------------------------------------------------------------
 note('\n## Scenario 3 (U3): three messages submitted while the first helper is busy');
 {
  const log = join(work, 'm3.jsonl');
  const state = newState({ helperDelayMs: 1500 });
  const srv = await world(state);
  const om = await startOmp({ config: { origin: srv.origin, providers: PROVIDERS, key: KEY, log }, extraArgs: ['--model', 'jevmain/main'] });
  await enable(om);
  const batch = [TASKS[0], TASKS[3], TASKS[4]];
  const sent = [];
  for (const t of batch) { sent.push(Date.now()); await om.prompt(t.text); }
  await om.waitFor(() => batch.every(t => shown(om).some(x => x.includes(t.text.slice(0, 40)) && x.startsWith('ANSWER['))), 'all three replies', 40000);
  const order = shown(om).filter(x => x.startsWith('ANSWER[')).map(x => x.slice(0, 60));
  note('submission offsets (ms):', JSON.stringify(sent.map(s => s - sent[0])), '| replies in order:', JSON.stringify(order));
  for (const t of batch) {
   const reply = shown(om).find(x => x.startsWith('ANSWER[') && x.includes(t.text.slice(0, 40)));
   assert.ok(reply.startsWith(`ANSWER[${t.model.split('/')[1]}]`), 'reply correlated with the right task and model');
  }
  note('host background skill-hint requests (separate from routed tasks, all local fixtures):', hostHints(srv).length);
  assert.deepEqual(helperEvents(srv).map(e => e.model), batch.map(t => t.model.split('/')[1]));
  assert.equal(classifyEvents(srv).length, 6);
  const records = await readLog(log);
  const ids = [...new Set(records.map(r => r.id))];
  note('distinct logged ids:', ids.length, '| per-id outcomes:', JSON.stringify(ids.map(id => records.filter(r => r.id === id).map(r => r.outcome).join('>'))));
  assert.equal(ids.length, 3);
  assert.ok(ids.every(id => records.filter(r => r.id === id && r.outcome === 'picked').length === 1));
  const firstHelperStart = helperEvents(srv)[0].at, secondClassify = classifyEvents(srv)[2].at, firstClassifyDone = classifyEvents(srv)[1].at;
  note('second message classified after the first helper request started (queued behind the busy helper):', secondClassify >= firstHelperStart, `(+${secondClassify - firstClassifyDone} ms after first pick)`);
  const noteOff = om.messages().length;
  await om.prompt('/jev off');
  await om.waitFor(() => om.messages().slice(noteOff).some(m => /routing off/.test(m.text)), 'off');
  note('Result: PASS (no message lost; one pick per message; replies correlate with their tasks)');
  await om.stop(); srv.close();
 }

 // ---- M4: F1 Jev unavailable ---------------------------------------------------------------------
 note('\n## Scenario 4 (F1): Jev unavailable (rejected request, server error, dropped connection, timeout, missing key)');
 {
  const log = join(work, 'm4.jsonl');
  const state = newState({ classify: '401' });
  const srv = await world(state);
  const om = await startOmp({ config: { origin: srv.origin, providers: PROVIDERS, key: KEY, log }, extraArgs: ['--model', 'jevmain/main'] });
  await enable(om);
  const cases = [['401', 'rejected request (HTTP 401)'], ['500', 'server error (HTTP 500)'], ['drop', 'dropped connection'], ['hang', 'timeout (no response for 30 s)']];
  for (const [mode, label] of cases) {
   state.classify = mode;
   const n = shown(om).filter(x => /failed or input was blocked/.test(x)).length;
   await om.prompt(`Task during ${mode}.`);
   await om.waitFor(() => shown(om).filter(x => /failed or input was blocked/.test(x)).length === n + 1, `error ${mode}`, 45000);
   note(`- ${label}: visible error shown; helper requests ${helperEvents(srv).length}; main-model requests ${mainEvents(srv).length}`);
  }
  const records = await readLog(log);
  note('logged error codes:', JSON.stringify(records.filter(r => r.outcome === 'error').map(r => r.errorCode)));
  assert.equal(records.filter(r => r.outcome === 'error').length, 4);
  assert.equal(helperEvents(srv).length, 0); assert.equal(mainEvents(srv).length, 0);
  assert.ok(!records.some(r => r.outcome === 'picked'), 'no invented difficulty/pick');
  assert.ok(!state.decisions.some(d => d.kind === 'difficulty'));
  note('shown error says no fallback model used:', shown(om).filter(x => /failed or input was blocked/.test(x)).every(x => /No fallback model was used/.test(x)));
  await om.stop(); srv.close();
  // missing key
  const state2 = newState();
  const srv2 = await world(state2);
  const om2 = await startOmp({ config: { origin: srv2.origin, providers: PROVIDERS, key: null, log: join(work, 'm4b.jsonl') }, extraArgs: ['--model', 'jevmain/main'] });
  await enable(om2);
  await om2.prompt('Task with no key available.');
  await om2.waitFor(() => om2.messages().some(m => m.role === 'assistant' && m.text === 'MAIN ANSWER'), 'normal answer');
  note('- missing key:', shown(om2).find(x => /remains off/.test(x)), `| Jev requests ${classifyEvents(srv2).length}, helper requests ${helperEvents(srv2).length}`);
  assert.equal(classifyEvents(srv2).length, 0); assert.equal(helperEvents(srv2).length, 0);
  note('Result: PASS');
  await om2.stop(); srv2.close();
 }

 // ---- M5: F2 selected helper unavailable ---------------------------------------------------------
 note('\n## Scenario 5 (F2): Jev selects a helper model whose provider rejects the credential');
 {
  const log = join(work, 'm5.jsonl');
  const state = newState({ forceModel: 'anthropic/broken-fixture' });
  const srv = await world(state);
  const om = await startOmp({ config: { origin: srv.origin, providers: PROVIDERS, key: KEY, log }, extraArgs: ['--model', 'jevmain/main'] });
  await enable(om);
  await om.prompt(TASKS[2].text);
  await om.waitFor(() => shown(om).some(x => /failed or input was blocked/.test(x)), 'helper failure', 60000);
  const pickLine = shown(om).find(x => x.includes('anthropic/broken-fixture'));
  const models = helperEvents(srv).map(e => e.model);
  note('route choice shown:', pickLine);
  note('provider calls by model:', JSON.stringify(models.reduce((a, m) => (a[m] = (a[m] || 0) + 1, a), {})), '| any other model invoked:', models.some(m => m !== 'broken-fixture'));
  assert.ok(models.length >= 1 && models.every(m => m === 'broken-fixture'));
  const records = await readLog(log);
  note('log:', records.map(r => `${r.outcome}${r.model ? ':' + r.model : ''}${r.errorCode ? ':' + r.errorCode : ''}`).join(', '));
  assert.ok(records.some(r => r.outcome === 'picked' && r.model === 'anthropic/broken-fixture'));
  assert.ok(records.some(r => r.outcome === 'error'));
  assert.ok(!records.some(r => r.outcome === 'success'));
  note('Result: PASS');
  await om.stop(); srv.close();
 }

 // ---- M6: F3 canary + unwritable log -----------------------------------------------------------------
 note('\n## Scenario 6 (F3): secret-like canary and an unwritable log');
 {
  const log = join(work, 'm6.jsonl');
  const state = newState();
  const srv = await world(state);
  const om = await startOmp({ config: { origin: srv.origin, providers: PROVIDERS, key: KEY, log }, extraArgs: ['--model', 'jevmain/main'] });
  await enable(om);
  await om.prompt(TASKS[0].text);
  await om.waitFor(() => shown(om).some(x => x.startsWith('ANSWER[')), 'benign answer');
  const before = srv.events.length;
  await om.prompt('Use token ghp_abcdefghijklmnopqrstuvwxyz0123456789 to log in and summarize.');
  await om.waitFor(() => shown(om).some(x => /failed or input was blocked/.test(x)), 'blocked canary');
  note('canary: requests sent to Jev/helpers =', srv.events.length - before);
  assert.equal(srv.events.length, before);
  const all = JSON.stringify(srv.events.map(e => e.raw)) + (await readFile(log, 'utf8')) + JSON.stringify(om.frames.map(f => f.e)) + om.stderr();
  note('canary text in requests, log, RPC frames or stderr:', all.includes('ghp_abcdef'), '| API key in any of them:', all.includes(KEY), '| log fields:', JSON.stringify([...new Set((await readLog(log)).flatMap(r => Object.keys(r)))].sort()));
  assert.ok(!all.includes('ghp_abcdef') && !all.includes(KEY));
  await om.stop(); srv.close();
  const state2 = newState();
  const srv2 = await world(state2);
  const om2 = await startOmp({ config: { origin: srv2.origin, providers: PROVIDERS, key: KEY, log: '/dev/null/unwritable/picks.jsonl' }, extraArgs: ['--model', 'jevmain/main'] });
  await enable(om2);
  await om2.prompt(TASKS[0].text);
  await om2.waitFor(() => shown(om2).some(x => /logging failure/.test(x)), 'logging failure message');
  const msg = shown(om2).filter(x => /logging failure|failed or input/.test(x));
  note('unwritable log: shown ->', JSON.stringify(msg));
  note('unwritable log: Jev requests', classifyEvents(srv2).length, '| helper requests', helperEvents(srv2).length, '(dispatch refused rather than silently unlogged)');
  assert.equal(classifyEvents(srv2).length, 0); assert.equal(helperEvents(srv2).length, 0);
  note('Result: PASS');
  await om2.stop(); srv2.close();
 }

 // ---- M7: R1 routing off ----------------------------------------------------------------------------------
 note('\n## Scenario 7 (R1): routing off, normal operation');
 {
  const state = newState();
  const srv = await world(state);
  const om = await startOmp({ config: { origin: srv.origin, providers: PROVIDERS, key: KEY, log: join(work, 'm7.jsonl') }, extraArgs: ['--model', 'jevmain/main'] });
  await om.prompt('/jev status');
  await om.waitFor(() => shown(om).some(x => /^Jev: off/.test(x)), 'status');
  note('/jev status ->', shown(om).find(x => /^Jev: off/.test(x)).slice(0, 60));
  await om.prompt('A normal question with routing off.');
  await om.waitFor(() => om.messages().some(m => m.role === 'assistant' && m.text === 'MAIN ANSWER'), 'main answer');
  note('network calls: Jev', classifyEvents(srv).length, '| helper', helperEvents(srv).length, '| main model', mainEvents(srv).length, '(message went straight to the main model)');
  assert.equal(classifyEvents(srv).length, 0); assert.equal(helperEvents(srv).length, 0); assert.equal(mainEvents(srv).length, 1);
  // existing slash commands remain available alongside /jev
  const callsBeforeCommand = srv.events.length;
  await om.prompt('/fixture-status');
  await om.waitFor(() => shown(om).includes('Existing fixture command handled'), 'other extension command');
  assert.equal(srv.events.length, callsBeforeCommand);
  note('Existing separately registered slash command handled by Omp; zero classifier/helper calls.');
  note('Result: PASS');
  await om.stop(); srv.close();
 }

 // ---- M8: R2 policy + approval ------------------------------------------------------------------------------
 note('\n## Scenario 8 (R2): helper inherits parent instructions and cannot bypass approvals');
 {
  const secret = join(work, 'approval-target.txt');
  await writeFile(secret, 'FILE-CANARY-CONTENT-4f9a');
  for (const approve of [false, true]) {
   const state = newState({ toolOnce: true, toolPath: secret, forceModel: 'anthropic/sonnet-fixture' });
   const srv = await world(state);
   const prompts = [];
   const om = await startOmp({ config: { origin: srv.origin, providers: PROVIDERS, key: KEY, log: join(work, `m8-${approve}.jsonl`) }, ui: { confirm: (title, message) => { if (/tool approval/.test(title)) { prompts.push(message); return approve; } return true; } }, extraArgs: ['--model', 'jevmain/main', '--append-system-prompt', MANDATORY] });
   await enable(om);
   await om.prompt(TASKS[2].text);
   await om.waitFor(() => shown(om).some(x => x.startsWith('TOOL-RESULT-SEEN')), 'tool result reply', 40000);
   const hlp = helperEvents(srv);
   const reply = shown(om).find(x => x.startsWith('TOOL-RESULT-SEEN'));
   note(`approval ${approve ? 'granted' : 'declined'}: parent received approval prompt (${prompts.length}) naming the tool call: ${/read/.test(prompts[0] || '')}; helper system prompt carries parent instructions: ${hlp[0].system.includes('Parent session instructions (remain binding)') && hlp[0].system.includes(MANDATORY)}`);
   note(`  helper's tool result -> ${reply.slice(0, 110)} | file content returned: ${reply.includes('FILE-CANARY-CONTENT')}`);
   assert.equal(prompts.length, 1);
   assert.ok(hlp[0].system.includes(MANDATORY));
   assert.equal(reply.includes('FILE-CANARY-CONTENT'), approve);
   if (!approve) assert.ok(/declined/i.test(reply));
   await om.stop(); srv.close();
  }
  note('Result: PASS');
 }
 note('\nALL /jev COMMAND RUNTIME SCENARIOS PASSED');
} finally {
 await rm(work, { recursive: true, force: true });
 if (outFile) await writeFile(outFile, `Omp ${(await exec('omp', ['--version'])).stdout.trim()}; real omp --mode rpc processes (isolated --profile), local fake Jev/Anthropic/Codex endpoints only, no paid calls.\nGenerated by: bun tools/jev-routing/runtime-matrix.mjs\n\n` + lines.join('\n') + '\n');
}
