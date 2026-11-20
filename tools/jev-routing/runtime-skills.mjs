// Skill-routing checks against a REAL `omp --mode rpc` process with local fake providers only.
// Covers jev-skill-routing U1, U2, F1, F2, F3, F4, F5, R2 (Omp runtime only).
//   TMPDIR=<dir with space> bun tools/jev-routing/runtime-skills.mjs [evidence-output-file]
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, readFile, rm } from 'node:fs/promises';
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
const MANDATORY = 'MANDATORY-SKILL: before any task read skill://mandatory-fixture first.';
const KEY = 'KEY-CANARY-7f3a9c41';
const work = await mkdtemp(join(process.env.JEV_TMP || tmpdir(), 'jev-skills-'));

// One fake world: a Jev classifier whose behaviour the scenario flips, plus a main model that
// obeys the mandatory-skill instruction (reads the skill) and otherwise answers.
function world(state) {
 return startServer(async ({ event, data, res }) => {
  if (event.path === '/classify') {
   const mode = state.classify;
   if (mode === '401') { json(res, {}, 401); return true; }
   if (mode === '500') { json(res, {}, 500); return true; }
   if (mode === 'drop') { res.destroy(); return true; }
   if (mode === 'hang') return true;
   const answers = {};
   for (const [id, q] of Object.entries(data.questions)) {
    const names = Object.keys(q.criteria);
    const choice = mode === 'unknown' ? 'no-such-skill' : state.pick(id, names);
    state.decisions.push({ seq: event.seq, id, options: names.length, hasNone: names.includes('__none__'), choice });
    answers[id] = { type: 'choice', choice };
   }
   json(res, { model: 'jev-1.14.0', answers, usage: { input_tokens: 100 } });
   return true;
  }
  const system = data.messages.filter(m => m.role === 'system' || m.role === 'developer').map(m => textOfContent(m.content)).join('\n');
  if (system.includes('MANDATORY-SKILL') && data.messages.at(-1)?.role === 'user') {
   sse(res, [{ role: 'assistant', tool_calls: [{ index: 0, id: 'mand-1', type: 'function', function: { name: 'read', arguments: JSON.stringify({ path: 'skill://mandatory-fixture' }) } }] }], 'tool_calls');
   return true;
  }
  sse(res, [{ role: 'assistant', content: 'MAIN ANSWER' }]);
  return true;
 });
}
const classifyEvents = s => s.events.filter(e => e.path === '/classify');
const mainEvents = s => s.events.filter(e => e.path !== '/classify');
const answers = om => om.messages().filter(m => m.role === 'assistant' && m.text === 'MAIN ANSWER').length;
const readLog = async p => { try { return (await readFile(p, 'utf8')).trim().split('\n').filter(Boolean).map(l => JSON.parse(l)); } catch { return []; } };
const showTimeline = (srv, om) => {
 const items = [];
 for (const e of srv.events) items.push({ at: e.at, text: e.path === '/classify' ? `Jev request: ${Object.keys(e.data.questions).join(',')} (${Object.values(e.data.questions).map(q => Object.keys(q.criteria).length).join(',')} options)` : `main model request #${e.seq} (${e.data.messages.filter(m => m.role !== 'system').length} non-system messages)` });
 for (const m of om.messages()) items.push({ at: m.at, text: `${m.role}${m.customType ? '/' + m.customType : ''}: ${m.text.replace(/\n/g, ' ').slice(0, 70)}` });
 items.sort((a, b) => a.at - b.at);
 const t0 = items[0]?.at ?? 0;
 for (const i of items) note(`  +${String(i.at - t0).padStart(5)}ms ${i.text}`);
};
async function project(name) {
 const dir = join(work, name);
 for (const s of ['mandatory-fixture', 'optional-alpha', 'optional-beta']) {
  await mkdir(join(dir, '.omp/skills', s), { recursive: true });
  await writeFile(join(dir, '.omp/skills', s, 'SKILL.md'), `---\nname: ${s}\ndescription: Fixture skill ${s} for routing checks\n---\nBODY-OF-${s}\n`);
 }
 return dir;
}
const mainArgs = ['--model', 'jevmain/main', '--append-system-prompt', MANDATORY];
const base = srv => ({ origin: srv.origin, providers: { jevmain: ['main'] }, key: KEY });

try {
 // ---- A/B: U1 + F1 + R2 -------------------------------------------------------------
 note('## Scenario 1 (U1, F1, R2): project skills + a system-mandated skill, Jev picks another optional skill, then None');
 {
  const cwd = await project('p1'), log = join(work, 'p1.jsonl');
  const state = { classify: 'pick', decisions: [], pick: (_id, names) => names.includes('optional-beta') ? 'optional-beta' : '__none__' };
  const srv = await world(state);
  const om = await startOmp({ cwd, config: { ...base(srv), skills: 'real-project', log }, extraArgs: mainArgs });
  await om.prompt('/jev skills on');
  await om.waitFor(() => om.messages().some(m => /^Jev skills\./.test(m.text)), 'enable');
  note('enable prompts:', om.uiRequests.filter(u => u.method !== 'setStatus' && u.method !== 'setWidget').map(u => `${u.method}: ${u.title}`).join(' | '));
  const task = 'Please research the topic of ocean tides.';
  await om.prompt(task);
  await om.waitFor(() => answers(om) === 1, 'first answer');
  // Case A: Jev chose a different optional skill. Mandatory skill must still be read.
  const j = classifyEvents(srv)[0], firstMain = mainEvents(srv)[0], second = mainEvents(srv)[1];
  const offered = Object.keys(Object.values(j.data.questions)[0].criteria).sort();
  note('Jev request options:', offered.join(', '));
  note('Jev request carries task text:', j.raw.includes(task), '| carries API key:', j.raw.includes(KEY), '| descriptions present:', Object.values(j.data.questions)[0].criteria['optional-alpha'].includes('Fixture skill'));
  assert.deepEqual(offered, ['__none__', 'mandatory-fixture', 'optional-alpha', 'optional-beta']);
  assert.ok(j.raw.includes(task) && !j.raw.includes(KEY) && j.authorization === 'present' && j.bearer === KEY);
  assert.ok(j.seq < firstMain.seq, 'Jev answered before the main model was called');
  const msgs = firstMain.data.messages;
  const sysText = msgs.filter(m => m.role === 'system' || m.role === 'developer').map(m => textOfContent(m.content)).join('\n');
  const idxSkill = msgs.findIndex(m => textOfContent(m.content).startsWith('[Selected skill: optional-beta'));
  const idxTask = msgs.findIndex(m => textOfContent(m.content).endsWith(task));
  note('main request: system prompt keeps mandatory instruction:', sysText.includes(MANDATORY), '| selected-skill message index', idxSkill, '< task message index', idxTask);
  assert.ok(sysText.includes(MANDATORY) && idxSkill >= 0 && idxTask > idxSkill);
  assert.ok(textOfContent(msgs[idxSkill].content).includes('BODY-OF-optional-beta'));
  const toolMsg = second.data.messages.find(m => m.role === 'tool');
  note('mandatory skill still loaded afterwards (tool result contains its body):', textOfContent(toolMsg?.content).includes('BODY-OF-mandatory-fixture'));
  assert.ok(textOfContent(toolMsg?.content).includes('BODY-OF-mandatory-fixture'));
  note('Timeline A (Jev picks optional-beta):');
  showTimeline(srv, om);
  // Case B: Jev answers None. No optional skill added; mandatory skill still read.
  state.pick = () => '__none__';
  const before = srv.events.length;
  await om.prompt('Tell me a fun fact about the moon.');
  await om.waitFor(() => answers(om) === 2, 'second answer');
  const later = srv.events.slice(before);
  const mainB = later.filter(e => e.path !== '/classify');
  const taskB = 'Tell me a fun fact about the moon.';
  const msgsB = mainB[0].data.messages;
  const idxB = msgsB.findIndex(m => textOfContent(m.content).endsWith(taskB));
  const prevB = textOfContent(msgsB[idxB - 1]?.content);
  note('Case B (None): message before the task is a selected-skill body:', prevB.startsWith('[Selected skill:'), '| main requests for this message:', mainB.length, '(mandatory read, then answer)');
  assert.ok(idxB > 0 && !prevB.startsWith('[Selected skill:'));
  assert.equal(mainB.length, 2);
  assert.ok(mainB[1].data.messages.slice(idxB).some(m => m.role === 'tool' && textOfContent(m.content).includes('BODY-OF-mandatory-fixture')));
  const records = await readLog(log);
  note('pick log outcomes:', records.map(r => `${r.outcome}${r.skill ? ':' + r.skill : ''}`).join(', '));
  const raw = await readFile(log, 'utf8');
  note('pick log contains task text:', raw.includes('ocean tides') || raw.includes('moon'), '| contains key:', raw.includes(KEY));
  assert.ok(!raw.includes('ocean tides') && !raw.includes('moon') && !raw.includes(KEY));
  assert.deepEqual(records.map(r => r.outcome), ['received', 'skill', 'received', 'skill']);
  assert.deepEqual(records.map(r => r.skill).filter(Boolean), ['optional-beta', 'None']);
  note('Result: PASS (Jev chose another optional skill, then None; system-mandated skill instruction and read were unaffected both times).');
  await om.stop(); srv.close();
 }

 // ---- D: F2 provider failures ---------------------------------------------------------
 note('\n## Scenario 2 (F2): provider errors and invalid choice; nothing loaded, nothing forwarded, not reported as None');
 {
  const cwd = await project('p2'), log = join(work, 'p2.jsonl');
  const state = { classify: '401', decisions: [], pick: (_id, names) => names.includes('optional-beta') ? 'optional-beta' : '__none__' };
  const srv = await world(state);
  const om = await startOmp({ cwd, config: { ...base(srv), skills: 'real-project', log }, extraArgs: mainArgs });
  await om.prompt('/jev skills on');
  await om.waitFor(() => om.messages().some(m => /^Jev skills\./.test(m.text)), 'enable');
  const cases = [['401', 'HTTP 401'], ['500', 'HTTP 500'], ['drop', 'connection dropped'], ['unknown', 'response names an unknown skill'], ['hang', 'no response (30 s client timeout)']];
  for (const [mode, label] of cases) {
   state.classify = mode;
   const nBefore = om.messages().filter(m => /failed or input was blocked/.test(m.text)).length;
   await om.prompt(`Question number ${mode}.`);
   await om.waitFor(() => om.messages().filter(m => /failed or input was blocked/.test(m.text)).length === nBefore + 1, 'error for ' + mode, 45000);
   note(`- ${label}: visible error shown; main model requests so far ${mainEvents(srv).length}`);
  }
  const records = await readLog(log);
  const errs = records.filter(r => r.outcome === 'error').map(r => r.errorCode);
  note('logged error codes:', JSON.stringify(errs));
  assert.equal(errs.length, 5);
  assert.deepEqual(errs, ['Jev HTTP 401 (no automatic retry)', 'Jev HTTP 500 (no automatic retry)', 'Jev request failed (no automatic retry)', 'Jev returned unknown choice', 'Jev request failed (no automatic retry)'].map(x => x));
  assert.equal(mainEvents(srv).length, 0, 'no failed task reached the main model');
  assert.ok(!records.some(r => r.outcome === 'skill'), 'no failure was logged as a skill pick or None');
  assert.ok(!om.messages().some(m => /\[Selected skill:/.test(m.text)));
  const shown = om.messages().filter(m => /failed or input was blocked/.test(m.text)).map(m => m.text);
  note('shown text includes "No fallback model was used":', shown.every(t => /No fallback model was used/.test(t)));
  // Healthy again: nothing stuck.
  state.classify = 'pick';
  await om.prompt('Now a healthy request.');
  await om.waitFor(() => answers(om) === 1, 'recovery answer');
  note('recovery after failures: main answered once; mandatory instruction still in system prompt:', mainEvents(srv)[0].data.messages.some(m => textOfContent(m.content).includes(MANDATORY)));
  note('Result: PASS');
  await om.stop(); srv.close();
 }

 // ---- E/F: F4 + F5 + missing key ------------------------------------------------------
 note('\n## Scenario 3 (F4, F5): no permission, zero budget, secret canary');
 {
  const cwd = await project('p3'), log = join(work, 'p3.jsonl');
  const state = { classify: 'pick', decisions: [], pick: () => '__none__' };
  const srv = await world(state);
  const ui = { confirm: () => false, input: () => '0.1' };
  const om = await startOmp({ cwd, ui, config: { ...base(srv), skills: 'real-project', log }, extraArgs: mainArgs });
  // F4a: user declines transmission.
  await om.prompt('/jev skills on');
  await om.waitFor(() => om.messages().some(m => /remains off/.test(m.text)), 'decline message');
  await om.prompt('Plain question after declined consent.');
  await om.waitFor(() => answers(om) === 1, 'plain answer');
  note('F4 no permission: message shown ->', om.messages().find(m => /remains off/.test(m.text)).text);
  note('F4 no permission: Jev requests =', classifyEvents(srv).length, '| task reached main model directly (routing off) =', mainEvents(srv).length > 0);
  assert.equal(classifyEvents(srv).length, 0);
  // F4b: permission given but zero budget.
  ui.confirm = () => true; ui.input = () => '0';
  const m0 = om.messages().length;
  await om.prompt('/jev skills on');
  await om.waitFor(() => om.messages().slice(m0).some(m => /remains off/.test(m.text)), 'zero budget message');
  await om.prompt('Plain question after zero budget.');
  await om.waitFor(() => answers(om) === 2, 'second plain answer');
  note('F4 zero budget: message shown ->', om.messages().slice(m0).find(m => /remains off/.test(m.text)).text);
  note('F4 zero budget: Jev requests =', classifyEvents(srv).length);
  assert.equal(classifyEvents(srv).length, 0);
  // F5: enabled with a valid budget; benign message works, canary is blocked before transmission.
  ui.input = () => '0.1';
  const m1 = om.messages().length;
  await om.prompt('/jev skills on');
  await om.waitFor(() => om.messages().slice(m1).some(m => /^Jev skills\./.test(m.text)), 'enabled');
  await om.prompt('Benign question about gardening.');
  await om.waitFor(() => answers(om) === 3, 'benign answer');
  const classifyBefore = classifyEvents(srv).length, mainBefore = mainEvents(srv).length;
  await om.prompt('My config is api_key=sk-FAKECANARY0123456789ab please summarize it.');
  await om.waitFor(() => om.messages().some(m => /failed or input was blocked/.test(m.text)), 'canary blocked');
  note('F5: Jev requests for canary message =', classifyEvents(srv).length - classifyBefore, '| main requests for canary =', mainEvents(srv).length - mainBefore);
  assert.equal(classifyEvents(srv).length, classifyBefore);
  assert.equal(mainEvents(srv).length, mainBefore);
  const everything = JSON.stringify(srv.events.map(e => e.raw)) + (await readFile(log, 'utf8')) + JSON.stringify(om.frames.map(f => f.e)) + om.stderr();
  note('F5: canary text anywhere (requests, log, RPC frames, stderr):', everything.includes('FAKECANARY'));
  assert.ok(!everything.includes('FAKECANARY'));
  const bearers = new Set(classifyEvents(srv).map(e => e.bearer));
  note('F5: API key used only as bearer header on Jev requests:', bearers.size === 1 && bearers.has(KEY), '| key in any request body/log/frame/stderr:', everything.includes(KEY));
  assert.ok(bearers.size === 1 && bearers.has(KEY) && !everything.includes(KEY));
  const records = await readLog(log);
  note('F5 log outcomes:', records.map(r => r.outcome + (r.errorCode ? ':' + r.errorCode : '')).join(', '));
  note('Result: PASS');
  await om.stop(); srv.close();
 }
 note('\n## Scenario 4 (F2/R3 missing key): routing stays off, existing behaviour preserved');
 {
  const cwd = await project('p4'), log = join(work, 'p4.jsonl');
  const state = { classify: 'pick', decisions: [], pick: () => '__none__' };
  const srv = await world(state);
  const om = await startOmp({ cwd, config: { ...base(srv), key: null, skills: 'real-project', log }, extraArgs: mainArgs });
  await om.prompt('/jev skills on');
  await om.waitFor(() => om.messages().some(m => /remains off/.test(m.text)), 'missing key message');
  await om.prompt('Normal question with routing unavailable.');
  await om.waitFor(() => answers(om) === 1, 'normal answer');
  note('missing key message ->', om.messages().find(m => /remains off/.test(m.text)).text);
  note('Jev requests =', classifyEvents(srv).length, '| main model received the message directly =', mainEvents(srv).length >= 1, '| mandatory skill read still happened =', mainEvents(srv).some(e => e.data.messages.some(m => m.role === 'tool' && textOfContent(m.content).includes('BODY-OF-mandatory-fixture'))));
  assert.equal(classifyEvents(srv).length, 0);
  note('Result: PASS');
  await om.stop(); srv.close();
 }

 // ---- G: U2 + F3 with a 300-skill catalogue (more than one Choice) ----------------------
 note('\n## Scenario 5 (U2, F3): 300 distinct skills discovered by real `omp skill list`, routed through the real extension and tournament');
 {
  const cwd = join(work, 'p5'), log = join(work, 'p5.jsonl');
  const catalogue = [];
  for (let i = 0; i < 300; i++) {
   const name = `fx-skill-${String(i).padStart(3, '0')}`;
   catalogue.push(name);
   await mkdir(join(cwd, '.omp/skills', name), { recursive: true });
   await writeFile(join(cwd, '.omp/skills', name, 'SKILL.md'), `---\nname: ${name}\ndescription: Distinct fixture capability number ${i} handling topic-${i * 7919 % 1000}\n---\nBODY-OF-${name}\n`);
  }
  const state = {
   classify: 'pick', decisions: [], calls: 0,
   // Choice 1 (group_0) prefers its first real candidate, Choice 2 (group_1) its last one; the fresh arbitration Choice
   // then compares the two winners jointly and prefers group_1's. Two plausible skills sit in different groups.
   pick: (id, names) => { state.calls++; return state.calls === 1 ? names[0] : state.calls === 2 ? names[names.length - 2] : names[1]; },
  };
  const srv = await world(state);
  const om = await startOmp({ cwd, config: { ...base(srv), skills: 'real-project', log }, extraArgs: ['--model', 'jevmain/main'] });
  await om.prompt('/jev skills on');
  await om.waitFor(() => om.messages().some(m => /^Jev skills\./.test(m.text)), 'enable', 30000);
  await om.prompt('Help me with a task that could fit several skills.');
  await om.waitFor(() => answers(om) === 1, 'answer', 60000);
  const reqs = classifyEvents(srv);
  const names = new Set();
  for (const e of reqs.slice(0, 2)) for (const n of Object.keys(Object.values(e.data.questions)[0].criteria)) if (n !== '__none__') names.add(n);
  note(`catalogue size ${catalogue.length}; Jev requests ${reqs.length}; Choice option counts incl. None: ${state.decisions.map(d => `#${state.decisions.indexOf(d) + 1} ${d.id}=${d.options}`).join(', ')}`);
  note('every Choice includes None:', state.decisions.every(d => d.hasNone), '| max options:', Math.max(...state.decisions.map(d => d.options)), '(limit 255)');
  note('all catalogue skills offered at least once:', catalogue.every(n => names.has(n)) && names.size === catalogue.length, `(${names.size}/${catalogue.length})`);
  assert.ok(names.size === catalogue.length && catalogue.every(n => names.has(n)) && state.decisions.every(d => d.hasNone && d.options <= 255));
  const [g0, g1, arb] = state.decisions;
  note('group winners (two plausible skills in different groups):', `${g0.id}->${g0.choice} ; ${g1.id}->${g1.choice}`);
  note('arbitration Choice (fresh, jointly normalised):', `${arb.options} options incl. None ->`, arb.choice);
  assert.equal(state.decisions.length, 3);
  assert.equal(arb.options, 3);
  assert.equal(arb.choice, g1.choice);
  assert.notEqual(g0.choice, g1.choice);
  const arbReq = reqs[2];
  assert.deepEqual(Object.keys(Object.values(arbReq.data.questions)[0].criteria).sort(), ['__none__', g0.choice, g1.choice].sort());
  const main1 = mainEvents(srv)[0].data.messages.find(m => textOfContent(m.content).startsWith(`[Selected skill: ${arb.choice};`));
  note('selected skill body injected into the main request:', Boolean(main1), '| group probabilities compared directly: never (each group is a separate request; only the fresh arbitration Choice compares the two winners)');
  assert.ok(main1);
  const rec = await readLog(log);
  note('pick log:', rec.map(r => `${r.outcome}${r.skill ? ':' + r.skill : ''}`).join(', '));
  note('Result: PASS');
  await om.stop(); srv.close();
 }
 note('\nALL SKILL-ROUTING RUNTIME SCENARIOS PASSED');
} finally {
 await rm(work, { recursive: true, force: true });
 if (outFile) await writeFile(outFile, `Omp ${(await exec('omp', ['--version'])).stdout.trim()}; real omp --mode rpc processes, local fake providers only, no paid calls.\nGenerated by: bun tools/jev-routing/runtime-skills.mjs\n\n` + lines.join('\n') + '\n');
}
