// R2: syntax and manifest checks.
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const failures = [];
const fail = (msg) => failures.push(msg);

function walk(dir, ext, out = []) {
  for (const name of readdirSync(dir)) {
    const p = path.join(dir, name);
    if (statSync(p).isDirectory()) walk(p, ext, out);
    else if (p.endsWith(ext)) out.push(p);
  }
  return out;
}

// 1. node --check on every extension .js
const jsFiles = walk(path.join(root, 'extension'), '.js');
for (const f of jsFiles) {
  const r = spawnSync(process.execPath, ['--check', f], { encoding: 'utf8' });
  if (r.status !== 0) fail(`node --check failed: ${path.relative(root, f)}\n${r.stderr}`);
}

// 2. manifest assertions
const ALLOWED = ['storage', 'unlimitedStorage', 'scripting', 'activeTab', 'debugger', 'tabs'];
let manifest;
try {
  manifest = JSON.parse(readFileSync(path.join(root, 'extension', 'manifest.json'), 'utf8'));
} catch (e) {
  fail(`manifest.json does not parse: ${e.message}`);
}
if (manifest) {
  if (manifest.manifest_version !== 3) fail('manifest_version must be 3');
  for (const p of manifest.permissions ?? []) {
    if (!ALLOWED.includes(p)) fail(`permission not allowed: ${p}`);
  }
  const hosts = manifest.host_permissions ?? [];
  if (hosts.length !== 1 || hosts[0] !== 'http://127.0.0.1/*') {
    fail(`host_permissions must be exactly ["http://127.0.0.1/*"], got ${JSON.stringify(hosts)}`);
  }
  const cs = manifest.content_scripts ?? [];
  if (cs.length === 0) fail('content_scripts missing');
  for (const c of cs) {
    if (!(c.matches ?? []).includes('<all_urls>')) fail('content script must match <all_urls>');
    if (c.all_frames !== true) fail('content script must set all_frames: true');
    for (const j of c.js ?? []) {
      try { statSync(path.join(root, 'extension', j)); } catch { fail(`content script file missing: ${j}`); }
    }
  }
}

// 3. every helper .py compiles
const helperDir = path.join(root, 'helper');
const pyFiles = walk(helperDir, '.py');
if (pyFiles.length) {
  // Same syntax check as py_compile, without writing .pyc files into the tree.
  const code = 'import sys\nfor f in sys.argv[1:]: compile(open(f, encoding="utf-8").read(), f, "exec")';
  const r = spawnSync('python3', ['-c', code, ...pyFiles], { encoding: 'utf8' });
  if (r.status !== 0) fail(`helper compile failed:\n${r.stderr}`);
}

if (failures.length) {
  console.error(failures.join('\n'));
  process.exit(1);
}
console.log(`check ok: ${jsFiles.length} js files, manifest, ${pyFiles.length} helper files`);
