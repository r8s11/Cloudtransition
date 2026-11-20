import assert from 'node:assert/strict';
import test from 'node:test';
import { foldPositions } from '../assets/atlas.js';

const vertices = [[-1.3, .05, .05], [-.12, 1.35, -.18], [1.25, .45, .06], [.8, -.9, -.12], [.04, -.25, .72], [-.78, -.88, -.02], [.02, -.65, -.12]];
const faces = [[0, 1, 4], [1, 2, 4], [2, 3, 4], [0, 4, 5], [5, 4, 6], [4, 3, 6]];

test('the finished fold exactly preserves the approved sculpture', () => {
  const expected = new Float32Array(faces.flatMap(face => face.flatMap(index => vertices[index])));
  assert.deepEqual(foldPositions(1), expected);
});

test('the sheet starts flat and gains the real ridge through finite intermediate poses', () => {
  const flat = foldPositions(0), half = foldPositions(.5), folded = foldPositions(1);
  for (let i = 0; i < flat.length; i += 3) {
    assert.equal(Math.abs(flat[i + 2]), 0);
    assert.ok(Number.isFinite(half[i]) && Number.isFinite(half[i + 1]) && Number.isFinite(half[i + 2]));
    assert.equal(half[i + 2], folded[i + 2] / 2);
  }
  assert.ok(half.some((value, i) => i % 3 === 2 && value > .3));
});

test('an output buffer can be reused without mutating a previously returned pose', () => {
  const completed = foldPositions(1), snapshot = completed.slice(), out = new Float32Array(54);
  assert.equal(foldPositions(.25, out), out);
  assert.deepEqual(completed, snapshot);
  foldPositions(1, out);
  assert.deepEqual(out, completed);
});
