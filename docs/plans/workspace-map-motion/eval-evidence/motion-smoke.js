// Run in the page's main-world console on the unfiltered Graph view.
(async () => {
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  assert(FILES.length >= 2, "Two indexed files required");
  closeDetail(false);
  openDetail(FILES[0], null, true);
  const start = performance.now();
  closeDetail(false, true);
  assert(document.getElementById("det").inert, "Closing drawer remains interactive");
  openDetail(FILES[1], null, true);
  const reversalMs = performance.now() - start;
  assert(reversalMs < 100, "Reversal did not exercise the sub-100ms race");
  await Promise.all(document.getElementById("det").getAnimations().map(animation => animation.finished.catch(() => {})));
  assert(!document.getElementById("det").hidden, "Old exit hid the new drawer");
  assert(document.querySelector("#det .pth").textContent === FILES[1].relativePath, "Old file replaced the latest selection");
  assert(SEL === FILES[1], "Selected file drifted");
  assert(!document.getElementById("det").inert, "Reopened drawer remains inert");
  const result = { status: "pass", reversalMs, selectedPath: FILES[1].relativePath };
  closeDetail(false);
  assert(document.getElementById("det").hidden, "Immediate dismissal delayed");
  console.log(result);
  return result;
})();
