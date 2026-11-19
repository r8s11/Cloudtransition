// Button Runner: one-click headless Claude skills (`claude -p`), local only.
// Each button maps to a fixed, server-side skill definition; the browser can only choose the
// skill, a question, and a model/effort from allowlists. No API key: the installed Claude CLI
// uses the account it is already signed in to.
const http = require('http');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const HOST = '127.0.0.1';
const PORT = Number(process.env.BUTTON_RUNNER_PORT) || 3939;
const LOG = path.join(__dirname, 'runs.log');
const WORKSPACE = path.resolve(__dirname, '..');
// Pin the Homebrew install: Node under Volta puts its own bin first on PATH, where a stale global
// Claude Code (2.1.78) lacks flags this server needs. CLAUDE_BIN overrides.
const HOMEBREW_CLAUDE = '/opt/homebrew/bin/claude';
const CLAUDE = process.env.CLAUDE_BIN || (fs.existsSync(HOMEBREW_CLAUDE) ? HOMEBREW_CLAUDE : 'claude');
const RUN_TIMEOUT_MS = 10 * 60 * 1000;
const MAX_BODY_BYTES = 16 * 1024;
const MAX_QUESTION_CHARS = 2000;
const BUDGET_USD = '1.00';

const MODELS = new Set(['', 'haiku', 'sonnet', 'opus']);
const EFFORTS = new Set(['', 'low', 'medium', 'high']);
const READ_ONLY_RESEARCH_TOOLS = 'Read,Glob,Grep,WebSearch,WebFetch';

const SKILLS = {
  research: {
    tools: READ_ONLY_RESEARCH_TOOLS,
    prompt: (question) =>
      'Research the question below. Use the files in the current workspace first, and the web only ' +
      'when the workspace does not answer it. Cite workspace file paths and verify every URL you ' +
      'cite by fetching it. Say plainly when the evidence is insufficient. Do not modify files.\n\n' +
      `Question: ${question}`,
  },
};

let running = false;

function log(entry) {
  fs.appendFileSync(LOG, JSON.stringify(entry) + '\n');
  console.log(`[run] ${entry.ts} ok=${entry.ok} skill=${entry.skill} ${entry.duration_ms}ms`);
}

function runClaude(skillId, question, model, effort) {
  const skill = SKILLS[skillId];
  const args = ['--print', '--output-format', 'json', '--no-session-persistence',
    '--tools', skill.tools, '--allowed-tools', skill.tools,
    '--permission-prompts', 'none', '--max-budget-usd', BUDGET_USD];
  if (model) args.push('--model', model);
  if (effort) args.push('--effort', effort);
  args.push(skill.prompt(question));

  return new Promise((resolve) => {
    const start = Date.now();
    const entry = { ts: new Date().toISOString(), skill: skillId, prompt: question,
      model: model || 'default', effort: effort || 'default' };
    const finish = (fields) => {
      Object.assign(entry, { duration_ms: Date.now() - start }, fields);
      log(entry);
      resolve(entry);
    };
    let stdout = '';
    let stderr = '';
    let child;
    try {
      child = spawn(CLAUDE, args, { cwd: WORKSPACE, stdio: ['ignore', 'pipe', 'pipe'] });
    } catch (e) {
      finish({ ok: false, output: '', error: `could not start claude: ${e.message}` });
      return;
    }
    const timer = setTimeout(() => child.kill('SIGTERM'), RUN_TIMEOUT_MS);
    child.stdout.on('data', (c) => { stdout += c; });
    child.stderr.on('data', (c) => { stderr += c; });
    child.on('error', (e) => {
      clearTimeout(timer);
      finish({ ok: false, output: '', error: `could not start claude: ${e.message}` });
    });
    child.on('close', (code, signal) => {
      clearTimeout(timer);
      if (signal) {
        finish({ ok: false, output: '', error: `stopped after ${RUN_TIMEOUT_MS / 60000} min (${signal})` });
        return;
      }
      let result;
      try {
        result = JSON.parse(stdout);
      } catch {
        finish({ ok: false, output: '', error: (stderr || stdout || `claude exited ${code}`).slice(0, 2000) });
        return;
      }
      const ok = code === 0 && !result.is_error;
      finish({
        ok,
        output: String(result.result || '').slice(0, 20000),
        error: ok ? null : String(result.result || stderr || `claude exited ${code}`).slice(0, 2000),
        cost_usd: result.total_cost_usd ?? null,
        models: Object.keys(result.modelUsage || {}),
      });
    });
  });
}

function send(res, status, type, body) {
  res.writeHead(status, {
    'Content-Type': type,
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'Content-Security-Policy': "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; frame-ancestors 'none'",
  });
  res.end(body);
}

const json = (res, status, obj) => send(res, status, 'application/json; charset=utf-8', JSON.stringify(obj));

// Only this machine's own page may drive it: loopback Host, same-origin Origin if sent.
function trusted(req) {
  const allowed = new Set([`127.0.0.1:${PORT}`, `localhost:${PORT}`]);
  if (!allowed.has(req.headers.host || '')) return false;
  const origin = req.headers.origin;
  return origin === undefined || allowed.has(origin.replace(/^http:\/\//, ''));
}

const server = http.createServer((req, res) => {
  if (!trusted(req)) { json(res, 403, { error: 'forbidden' }); return; }

  if (req.method === 'GET' && (req.url === '/' || req.url === '/index.html')) {
    send(res, 200, 'text/html; charset=utf-8', fs.readFileSync(path.join(__dirname, 'index.html')));
    return;
  }

  if (req.method === 'GET' && req.url === '/runs') {
    const lines = fs.existsSync(LOG) ? fs.readFileSync(LOG, 'utf8').trim().split('\n').slice(-50) : [];
    json(res, 200, lines.map((l) => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean));
    return;
  }

  if (req.method === 'POST' && req.url === '/run') {
    if ((req.headers['content-type'] || '').split(';')[0].trim() !== 'application/json') {
      json(res, 415, { error: 'Content-Type must be application/json' });
      return;
    }
    let body = '';
    let tooLarge = false;
    req.on('data', (c) => {
      body += c;
      if (body.length > MAX_BODY_BYTES) { tooLarge = true; req.destroy(); }
    });
    req.on('end', async () => {
      if (tooLarge) return;
      let input;
      try { input = JSON.parse(body); } catch { json(res, 400, { error: 'body is not valid JSON' }); return; }
      const skill = String(input.skill || '');
      const question = String(input.question || '').trim();
      const model = String(input.model || '');
      const effort = String(input.effort || '');
      if (!Object.hasOwn(SKILLS, skill)) { json(res, 400, { error: 'unknown skill' }); return; }
      if (!question) { json(res, 400, { error: 'question is required' }); return; }
      if (question.length > MAX_QUESTION_CHARS) { json(res, 400, { error: `question over ${MAX_QUESTION_CHARS} characters` }); return; }
      if (!MODELS.has(model) || !EFFORTS.has(effort)) { json(res, 400, { error: 'unsupported model or effort' }); return; }
      if (running) { json(res, 409, { error: 'a run is already in progress' }); return; }
      running = true;
      try {
        json(res, 200, await runClaude(skill, question, model, effort));
      } finally {
        running = false;
      }
    });
    return;
  }

  json(res, 404, { error: 'not found' });
});

server.listen(PORT, HOST, () => console.log(`Button runner: http://${HOST}:${PORT}`));
