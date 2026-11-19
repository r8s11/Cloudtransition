import test from 'node:test';
import assert from 'node:assert/strict';
import { constellationLayout } from '../assets/constellation.js';

function fixture() {
  const alpha = { key: 'Alpha', label: 'Alpha', color: 'var(--graph-c1)', owned: [], count: 2 };
  const beta = { key: 'Beta', label: 'Beta', color: 'var(--graph-c2)', owned: [], count: 2 };
  const files = [
    { f: { relativePath: 'docs/a.md', name: 'a.md', topics: ['Alpha', 'Beta'] }, groups: [beta, alpha], x: 0, y: 0 },
    { f: { relativePath: 'docs/b.md', name: 'b.md', topics: ['Beta'] }, groups: [beta], x: 4, y: -2 },
    { f: { relativePath: 'notes/雪.md', name: '雪.md', topics: ['Alpha'] }, groups: [alpha], x: -8, y: 2 },
  ];
  alpha.owned.push(files[0], files[2]);
  beta.owned.push(files[1]);
  return { groups: [alpha, beta], files };
}

function freeze(value, seen = new WeakSet()) {
  if (!value || typeof value !== 'object' || seen.has(value)) return value;
  seen.add(value);
  for (const child of Object.values(value)) freeze(child, seen);
  return Object.freeze(value);
}

test('coordinates and membership identities survive source ordering changes', () => {
  const input = fixture();
  const first = constellationLayout(input);
  const reordered = {
    groups: [...input.groups].reverse(),
    files: [...input.files].reverse().map(point => ({ ...point, groups: [...point.groups].reverse() })),
  };
  assert.deepEqual(constellationLayout(input), first);
  assert.deepEqual(constellationLayout(reordered), first);
  assert.ok(new Set(first.files.map(file => file.z)).size > 1, 'layout has actual depth');
});

test('every distinct actual path occurs once, including equal names in separate folders', () => {
  const input = fixture();
  input.files.push({ ...input.files[0], groups: [...input.files[0].groups] });
  input.files.push({ f: { relativePath: 'other/a.md', name: 'a.md' }, groups: [] });
  const result = constellationLayout(input);
  const expected = [...new Set(input.files.map(point => point.f.relativePath))].sort();
  assert.deepEqual(result.files.map(file => file.path), expected);
  assert.equal(new Set(result.files.map(file => file.path)).size, result.files.length);
  for (const file of result.files) {
    assert.equal(file.f, input.files.find(point => point.f.relativePath === file.path).f);
  }
});

test('edges deduplicate memberships and never target absent groups or invented topics', () => {
  const input = fixture();
  input.files[0].groups.push(input.groups[0], { key: 'Absent' });
  input.files.push({ ...input.files[0], groups: [input.groups[1], input.groups[1]] });
  input.files[1].f.topics.push('Not a layout membership');
  const result = constellationLayout(input);
  assert.deepEqual(result.edges.map(edge => [edge.path, edge.key]), [
    ['docs/a.md', 'Alpha'], ['docs/a.md', 'Beta'], ['docs/b.md', 'Beta'], ['notes/雪.md', 'Alpha'],
  ]);
  for (const edge of result.edges) {
    assert.equal(result.files[edge.fileIndex].path, edge.path);
    assert.equal(result.groups[edge.groupIndex].key, edge.key);
    assert.ok(result.files[edge.fileIndex].groups.includes(edge.key));
  }
});

test('all file and hub coordinates remain finite for singletons and many clusters', () => {
  const groups = Array.from({ length: 45 }, (_, i) => ({ key: String(i), label: String(i) }));
  const input = {
    groups,
    files: Array.from({ length: 260 }, (_, i) => ({
      f: { relativePath: `folder/${i}.md`, name: `${i}.md` }, groups: [groups[i % groups.length]],
    })),
  };
  for (const node of [...constellationLayout(input).files, ...constellationLayout(input).groups]) {
    for (const axis of ['x', 'y', 'z', 'radius']) assert.ok(Number.isFinite(node[axis]), `${node.key || node.path}: ${axis}`);
    assert.ok(node.radius > 0);
  }
});

test('empty input stays empty without synthetic files or hubs', () => {
  assert.deepEqual(constellationLayout({ groups: [], files: [] }), { groups: [], files: [], edges: [] });
  assert.deepEqual(constellationLayout(), { groups: [], files: [], edges: [] });
});

test('root, untagged and membership-free files preserve only supplied identities', () => {
  const root = { key: '__root__', label: 'Workspace root' };
  const untagged = { key: '__untagged__', label: 'Untagged' };
  const input = { groups: [root, untagged], files: [
    { f: { relativePath: 'root.md', name: 'root.md', topics: [] }, groups: [root] },
    { f: { relativePath: 'notes/plain.md', name: 'plain.md', topics: [] }, groups: [untagged] },
    { f: { relativePath: 'loose.md', name: 'loose.md', topics: ['Not an edge'] }, groups: [] },
  ] };
  const result = constellationLayout(input);
  assert.equal(result.files.length, 3);
  assert.deepEqual(result.edges.map(edge => [edge.path, edge.key]), [
    ['notes/plain.md', '__untagged__'], ['root.md', '__root__'],
  ]);
  assert.deepEqual(result.files.find(file => file.path === 'loose.md').groups, []);
  assert.ok(result.files.every(file => [file.x, file.y, file.z].every(Number.isFinite)));
});

test('layout never changes frozen source objects or cyclic owned memberships', () => {
  const input = fixture();
  const before = structuredClone(input);
  freeze(input);
  const result = constellationLayout(input);
  assert.deepEqual(input, before);
  assert.notEqual(result.files, input.files);
  assert.notEqual(result.groups, input.groups);
  assert.equal(result.files[0].f, input.files[0].f);
});
