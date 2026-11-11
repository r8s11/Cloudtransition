import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const manifest = JSON.parse(
  readFileSync(fileURLToPath(new URL('../../extension/manifest.json', import.meta.url)), 'utf8'),
);

test('manifest: MV3 with the allowed permission set', () => {
  const allowed = ['storage', 'unlimitedStorage', 'scripting', 'activeTab', 'debugger', 'tabs'];
  assert.equal(manifest.manifest_version, 3);
  for (const p of manifest.permissions) assert.ok(allowed.includes(p), `unexpected permission ${p}`);
  assert.deepEqual(manifest.host_permissions, ['http://127.0.0.1/*']);
});
