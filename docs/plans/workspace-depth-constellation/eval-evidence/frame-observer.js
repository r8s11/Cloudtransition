// Test-only main-world instrumentation, applied after scene initialization.
// Captures real rAF cadence and the CPU cost of callbacks that submit GPU draws.
(() => {
  const proof = window.__depthGPU;
  if (!proof || window.__depthFrameObserver) return;
  window.__depthFrameObserver = true;
  proof.renderTasks = [];
  const original = window.requestAnimationFrame;
  window.requestAnimationFrame = function (callback) {
    return original.call(this, timestamp => {
      const draws = proof.draws;
      const start = performance.now();
      try { callback(timestamp); }
      finally {
        if (proof.draws !== draws) proof.renderTasks.push({ timestamp, duration: performance.now() - start, draws: proof.draws - draws });
        if (proof.renderTasks.length > 600) proof.renderTasks.splice(0, 300);
      }
    });
  };
})();
