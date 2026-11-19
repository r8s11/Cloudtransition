// Run after an uninterrupted fresh 3D load with normal motion and GSAP available.
// The browser runner installs a read-only Scene.onAfterRender probe as __observatory.
(() => {
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const frames = window.__observatory?.frames || [];
  assert(frames.some(frame => frame.scale > 0 && frame.scale < 0.99),
    'Initial layout resize swallowed the first 3D entrance');
  assert(frames.every(frame => Number.isFinite(frame.scale) && frame.scale > 0),
    'Entrance hid or invalidated a real file glyph');
  assert(Math.abs(frames.at(-1).scale - 1) < 0.00001,
    'Entrance did not settle at the final glyph size');
  assert(frames.every(frame => frame.calls <= 6 && frame.triangles <= 250000),
    '3D scene exceeded its agreed rendering budget');
  const fps = (frames.length - 1) * 1000 / (frames.at(-1).t - frames[0].t);
  assert(fps >= 50, 'Nested animation frames reduced entrance rendering below 50fps');
  return { status: 'pass', frames: frames.length, fps };
})();
