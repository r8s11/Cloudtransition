// Shared test harness for the real-Omp-process runtime checks. Local fake providers only:
// every Anthropic/OpenAI/Codex base URL is redirected to a 127.0.0.1 server, so no check here
// can reach a paid provider or TypeSafe.
import http from 'node:http';
import { spawn, spawnSync } from 'node:child_process';
import readline from 'node:readline';
import { fileURLToPath } from 'node:url';
import { rmSync, mkdtempSync } from 'node:fs';
import { homedir, tmpdir } from 'node:os';
import { join, relative } from 'node:path';

export const FIXTURE = fileURLToPath(new URL('./fixture.mjs', import.meta.url));

export function sse(res, parts, finish = 'stop', usage = { prompt_tokens: 10, completion_tokens: 5, total_tokens: 15 }) {
 res.writeHead(200, { 'Content-Type': 'text/event-stream' });
 const chunk = (delta, fr = null, extra = {}) => res.write('data: ' + JSON.stringify({ id: 'fx', object: 'chat.completion.chunk', created: 1, model: 'fx', choices: [{ index: 0, delta, finish_reason: fr }], ...extra }) + '\n\n');
 for (const p of parts) chunk(p);
 chunk({}, finish, { usage });
 res.end('data: [DONE]\n\n');
}
export const textOfContent = c => typeof c === 'string' ? c : Array.isArray(c) ? c.map(p => p.text ?? '').join('') : JSON.stringify(c ?? '');

// respond({event,data,res}) must answer and return true, or return false to get a 404.
export async function startServer(respond) {
 const events = [];
 let seq = 0;
 const t0 = Date.now();
 const server = http.createServer(async (req, res) => {
  let body = '';
  for await (const part of req) body += part;
  let data = {};
  try { data = JSON.parse(body || '{}'); } catch { /* not JSON */ }
  const event = { seq: ++seq, at: Date.now(), tMs: Date.now() - t0, path: req.url, model: data.model, authorization: req.headers.authorization ? 'present' : 'absent', bearer: req.headers.authorization?.replace(/^Bearer /, ''), bytes: Buffer.byteLength(body) };
  const rec = { ...event, data, raw: body };
  res.once('finish',()=>{rec.respondedAt=Date.now();});
  events.push(rec);
  if (!(await respond({ event: rec, data, res, events }))) { res.writeHead(404); res.end(); }
 });
 await new Promise(r => server.listen(0, '127.0.0.1', r));
 return {
  events, origin: `http://127.0.0.1:${server.address().port}`,
  close() { server.closeAllConnections(); server.close(); },
  count: f => events.filter(f).length,
 };
}
// Helper sessions resolve credentials through Omp's auth storage, not the extension's provider registration,
// so the isolated profile is seeded with a fixture-only key (never a real credential) for each helper provider.
function seedFixtureAuth(profile, providers, env) {
 if (!providers.length) return;
 const credentials = providers.map(provider => ({ provider, credential: { type: 'api_key', key: 'fixture-local-only' } }));
 const r = spawnSync('omp', ['--profile', profile, 'auth', 'import', '-'], { input: JSON.stringify({ version: 1, credentials }), encoding: 'utf8', env });
 if (r.status !== 0) throw Error('Could not seed fixture credentials: ' + r.stderr);
}
let profileSeq = 0;
// Spawn `omp --mode rpc` with the Jev fixture. `config` is handed to fixture.mjs. Each run gets a fresh profile
// (own auth, settings, caches) that holds only fixture credentials for the providers the scenario registers.
export async function startOmp({ config, ui = {}, extraArgs = [], env = {}, cwd = process.cwd(), profile = `jev-rt-${process.pid}-${++profileSeq}` }) {
 const state=mkdtempSync(join(tmpdir(),'jev-omp-state-'));
 // Omp resolves PI_CONFIG_DIR relative to HOME; keep HOME normal and all fixture
 // auth/settings/cache on the external test volume instead of the full internal disk.
 const base = { ...process.env, PI_CONFIG_DIR:relative(homedir(),join(state,'config')), PI_CODING_AGENT_DIR:join(state,'agent'), ...env };
 delete base.TYPESAFE_API_KEY;
 try { seedFixtureAuth(profile, Object.keys(config.providers || {}).filter(p => p !== 'jevmain'), base); }
 catch(error) {rmSync(state,{recursive:true,force:true});throw error;}
 const child = spawn('omp', ['--mode', 'rpc', '--profile', profile, '--no-extensions', '-e', FIXTURE, '--no-session', '--no-title', '--no-lsp', '--no-context-files', '--no-rules', ...extraArgs], {
  cwd, env: { ...base, JEV_FIXTURE: JSON.stringify(config) }, stdio: ['pipe', 'pipe', 'pipe'],
 });
 let stderr = '';
 child.stderr.on('data', b => { stderr += b; });
 const frames = [], uiRequests = [], pending = new Map();
 let seq = 0, readyResolve;
 const ready = new Promise(r => { readyResolve = r; });
 const send = m => child.stdin.write(JSON.stringify(m) + '\n');
 const line = readline.createInterface({ input: child.stdout });
 line.on('line', s => {
  let e; try { e = JSON.parse(s); } catch { return; }
  frames.push({ at: Date.now(), e });
  if (e.type === 'ready') readyResolve();
  if (e.type === 'extension_ui_request') {
   uiRequests.push({ method: e.method, title: e.title, at: Date.now() });
   if (e.method === 'input') send({ type: 'extension_ui_response', id: e.id, value: ui.input?.(e.title) ?? '0.1' });
   else if (e.method === 'confirm') send({ type: 'extension_ui_response', id: e.id, confirmed: ui.confirm ? !!ui.confirm(e.title, e.message) : true });
   else if (['select', 'editor'].includes(e.method)) send({ type: 'extension_ui_response', id: e.id, cancelled: true });
  }
  if (e.type === 'response' && pending.has(e.id)) { const p = pending.get(e.id); pending.delete(e.id); e.success ? p.resolve(e) : p.reject(Error(e.error)); }
 });
 const prompt = message => new Promise((resolve, reject) => { const id = 'p' + (++seq); pending.set(id, { resolve, reject }); send({ id, type: 'prompt', message }); });
 const messages = () => frames.filter(f => f.e.type === 'message_end').map(f => ({ at: f.at, role: f.e.message?.role, customType: f.e.message?.customType, text: textOfContent(f.e.message?.content) }));
 async function waitFor(predicate, what, ms = 30000) {
  const end = Date.now() + ms;
  while (!predicate()) {
   if (child.exitCode !== null) throw Error('Omp exited early: ' + stderr.slice(-800));
   if (Date.now() > end) throw Error('Timed out waiting for ' + what + '; shown: ' + JSON.stringify(messages().filter(m => m.role === 'custom').map(m => m.text)).slice(-1500) + '; stderr tail: ' + stderr.slice(-600));
   await new Promise(r => setTimeout(r, 20));
  }
 }
 const stop = async () => { child.kill(); line.close(); await new Promise(r => setTimeout(r, 300)); rmSync(state, { recursive: true, force: true }); };
 let readyTimer;
 try { await Promise.race([ready, new Promise((_, rej) => {readyTimer=setTimeout(() => rej(Error('omp not ready: ' + stderr.slice(-600))), 40000);})]); }
 catch(error) {await stop();throw error;} finally {clearTimeout(readyTimer);}
 return { child, frames, uiRequests, prompt, messages, waitFor, stop, stderr: () => stderr, profile };
}
