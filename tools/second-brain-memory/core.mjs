import { spawn } from 'node:child_process';
import { access, stat } from 'node:fs/promises';
import { constants } from 'node:fs';
import { isAbsolute, join } from 'node:path';

export const DEFAULT_ROOT = '/Volumes/SANDISK USB/work/Cloudtransition';
export class BrainAdapterError extends Error {
  constructor(code) { super(`Second Brain unavailable: ${code}`); this.name = 'BrainAdapterError'; this.code = code; }
}
const invalid = () => ({exitCode: 2, payload: {status: 'error', error: 'invalid_input', message: 'Invalid Second Brain parameters or unsupported fields.'}});
const keysAre = (value, allowed) => value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).every(k => allowed.includes(k));

export function createBrainClient({root = DEFAULT_ROOT, python = 'python3', script = join(root, 'second-brain/brain.py'), timeoutMs = 15000, maxBuffer = 1048576} = {}) {
  if (!isAbsolute(root) || !isAbsolute(script) || !Number.isFinite(timeoutMs) || timeoutMs <= 0 || !Number.isInteger(maxBuffer) || maxBuffer < 1) throw new BrainAdapterError('invalid_configuration');
  async function run(args, signal) {
    if (signal?.aborted) throw new BrainAdapterError('cancelled');
    try {
      if (!(await stat(root)).isDirectory()) throw new Error();
      await access(root, constants.R_OK | constants.X_OK);
      await access(join(root, 'second-brain'), constants.R_OK | constants.X_OK);
      await access(script, constants.R_OK);
    } catch { throw new BrainAdapterError('storage_unavailable'); }
    return new Promise((resolve, reject) => {
      let child, timer, failure, size = 0;
      const chunks = [];
      const stop = code => { if (!failure) failure = code; child?.kill('SIGKILL'); };
      const cancel = () => stop('cancelled');
      try { child = spawn(python, [script, '--root', root, ...args], {cwd: root, shell: false, stdio: ['ignore', 'pipe', 'pipe']}); }
      catch { reject(new BrainAdapterError('process_unavailable')); return; }
      timer = setTimeout(() => stop('timeout'), timeoutMs);
      signal?.addEventListener('abort', cancel, {once: true});
      if (signal?.aborted) cancel();
      const collect = (chunk, keep) => {
        size += chunk.length;
        if (size > maxBuffer) stop('output_limit');
        else if (keep) chunks.push(chunk);
      };
      child.stdout.on('data', b => collect(b, true));
      child.stderr.on('data', b => collect(b, false));
      child.on('error', () => { failure ??= 'process_unavailable'; });
      child.on('close', (exitCode, exitSignal) => {
        clearTimeout(timer); signal?.removeEventListener('abort', cancel);
        if (failure) { reject(new BrainAdapterError(failure)); return; }
        if (exitSignal || !Number.isInteger(exitCode) || exitCode < 0 || exitCode > 4) { reject(new BrainAdapterError('process_failed')); return; }
        let payload;
        try { payload = JSON.parse(Buffer.concat(chunks).toString('utf8')); }
        catch { reject(new BrainAdapterError('invalid_json')); return; }
        if (!payload || typeof payload !== 'object' || Array.isArray(payload) || typeof payload.status !== 'string' || (exitCode === 0 && payload.status === 'error')) {
          reject(new BrainAdapterError('invalid_response')); return;
        }
        resolve({exitCode, payload});
      });
    });
  }
  return {
    recall(params, {signal} = {}) {
      if (!keysAre(params, ['query']) || typeof params.query !== 'string' || !params.query.trim() || [...params.query].length > 500) return Promise.resolve(invalid());
      return run(['query', '--', params.query], signal);
    },
    remember(params, {signal} = {}) {
      if (!keysAre(params, ['title', 'summary', 'body', 'supersedes']) || !['title', 'summary', 'body'].every(k => typeof params[k] === 'string') || (params.supersedes !== undefined && (!Array.isArray(params.supersedes) || !params.supersedes.every(id => typeof id === 'string')))) return Promise.resolve(invalid());
      const args = ['remember', `--title=${params.title}`, `--summary=${params.summary}`, `--body=${params.body}`];
      for (const id of params.supersedes ?? []) args.push(`--supersedes=${id}`);
      return run(args, signal);
    },
  };
}
