// Install as a browser init script before navigating to /workspace-map/?view=graph.
// Observes real Three.js rendering and disposal; it never changes scene state.
(async () => {
  if (!location.href.startsWith('http://127.0.0.1:8000/workspace-map/')) return;
  const THREE = await import('/workspace-map/assets/vendor/three.module.min.js');
  const probe = window.__observatory = {
    frames: [], renders: 0, scenes: [], disposedGeometries: 0,
    disposedMaterials: 0, visibility: [],
  };
  document.addEventListener('visibilitychange', () => {
    probe.visibility.push({ t: performance.now(), hidden: document.hidden });
  });
  const after = THREE.Scene.prototype.onAfterRender;
  THREE.Scene.prototype.onAfterRender = function (renderer, scene, camera) {
    const files = scene.children.find(child => child.isInstancedMesh);
    if (files) {
      probe.renders++;
      probe.current = { renderer, scene, camera };
      if (!probe.scenes.some(entry => entry.scene === scene)) probe.scenes.push(probe.current);
      let minScale = Infinity;
      for (let index = 0; index < files.count; index++) {
        minScale = Math.min(minScale, files.instanceMatrix.array[index * 16]);
      }
      probe.frames.push({
        t: performance.now(), calls: renderer.info.render.calls,
        triangles: renderer.info.render.triangles,
        scale: files.instanceMatrix.array[0], minScale,
      });
    }
    return after.apply(this, arguments);
  };
  for (const [type, key] of [
    [THREE.BufferGeometry, 'disposedGeometries'], [THREE.Material, 'disposedMaterials'],
  ]) {
    const dispose = type.prototype.dispose;
    type.prototype.dispose = function () {
      probe[key]++;
      return dispose.apply(this, arguments);
    };
  }
})();
