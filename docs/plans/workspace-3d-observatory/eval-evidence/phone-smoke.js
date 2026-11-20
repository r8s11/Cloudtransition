// Run on the real 3D Graph at 390x844 after it settles.
(() => {
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const graph = document.querySelector('.graph-3d').getBoundingClientRect();
  const canvas = document.querySelector('.constellation-canvas').getBoundingClientRect();
  assert(canvas.bottom <= graph.bottom && canvas.top >= graph.top,
    'Phone graph shell clips the fitted 3D scene');
  assert(canvas.left >= graph.left && canvas.right <= graph.right,
    'Phone graph shell clips the scene horizontally');
  assert(document.documentElement.scrollWidth <= innerWidth, 'Phone page overflows horizontally');
  return { status: 'pass', sceneBottom: canvas.bottom, shellBottom: graph.bottom };
})();
