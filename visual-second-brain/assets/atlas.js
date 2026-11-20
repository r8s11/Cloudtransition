// Optional Folded Atlas enhancement. Three.js r180 is shipped locally (MIT).
// The map owns file state; this module owns only the sculpture and its lifetime.
const FOLD_VERTICES = [
  [-1.3, 0.05, 0.05], [-0.12, 1.35, -0.18], [1.25, 0.45, 0.06],
  [0.8, -0.9, -0.12], [0.04, -0.25, 0.72], [-0.78, -0.88, -0.02], [0.02, -0.65, -0.12],
];
const FOLD_FACES = [[0, 1, 4], [1, 2, 4], [2, 3, 4], [0, 4, 5], [5, 4, 6], [4, 3, 6]];

export function foldPositions(progress, out = new Float32Array(54)) {
  const spread = 1 + (1 - progress) * 0.1;
  for (let i = 0; i < FOLD_FACES.length; i++) {
    for (let j = 0; j < 3; j++) {
      const vertex = FOLD_VERTICES[FOLD_FACES[i][j]], offset = i * 9 + j * 3;
      out[offset] = vertex[0] * spread;
      out[offset + 1] = vertex[1] * spread;
      out[offset + 2] = vertex[2] * progress;
    }
  }
  return out;
}

export function createAtlas(host, motionButton) {
  const stage = host.querySelector(".atlas-stage");
  const wide = matchMedia("(min-width: 1100px)");
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  const events = new AbortController();
  const { signal } = events;
  let available = false, working = false, paused = false, visible = false;
  let disposed = false, failed = false, loading = false, suspended = false;
  let renderer = null, scene = null, camera = null, paper = null, canvas = null;
  let resources = [], raf = 0, lastTime = 0, idleTime = 0;
  let topic = "", targetY = -0.32, startY = targetY, progress = 1;
  let width = 0, height = 0;
  let foldGeometry = null, foldProgress = 1;

  function stop() {
    cancelAnimationFrame(raf);
    raf = 0;
    lastTime = 0;
  }

  function release() {
    stop();
    host.classList.remove("atlas-rendered");
    motionButton.hidden = true;
    if (canvas) canvas.removeEventListener("webglcontextlost", contextLost);
    for (const resource of resources) resource.dispose();
    resources = [];
    if (renderer) {
      renderer.dispose();
      renderer.forceContextLoss();
    }
    if (canvas) canvas.remove();
    renderer = scene = camera = paper = canvas = null;
    foldGeometry = null;
  }

  function contextLost() {
    failed = true;
    release();
  }

  function onScreen() {
    return !disposed && !failed && available && visible && !document.hidden && !suspended && wide.matches && width > 0 && height > 0;
  }

  function moving() {
    return onScreen() && !paused && !reduced.matches && foldProgress === 1;
  }

  function draw() {
    if (!renderer || !onScreen()) return;
    try {
      renderer.render(scene, camera);
    } catch {
      // Optional GPU failure must never become a file-index failure.
      failed = true;
      release();
    }
  }

  function tick(time) {
    raf = 0;
    if (!renderer || !moving()) return;
    const dt = lastTime ? Math.min((time - lastTime) / 1000, 0.04) : 0;
    lastTime = time;
    if (progress < 1) {
      progress = Math.min(1, progress + dt / 0.22);
      const ease = progress === 1 ? 1 : 1 - 2 ** (-10 * progress);
      paper.rotation.y = startY + (targetY - startY) * ease;
    } else if (!working && foldProgress === 1) {
      idleTime += dt;
      paper.rotation.y = targetY + Math.sin(idleTime * 0.38) * 0.055;
      paper.rotation.x = -0.14 + Math.sin(idleTime * 0.31) * 0.025;
      paper.position.y = Math.sin(idleTime * 0.65) * 0.045;
    }
    draw();
    if (renderer && moving() && (progress < 1 || !working)) raf = requestAnimationFrame(tick);
    else lastTime = 0;
  }

  function schedule() {
    if (renderer && moving() && (progress < 1 || !working) && !raf) raf = requestAnimationFrame(tick);
  }

  function resize() {
    width = stage.clientWidth;
    height = stage.clientHeight;
    if (!renderer || !width || !height) {
      if (!width || !height) stop();
      return;
    }
    renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 1.5));
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    draw();
  }

  function controls() {
    motionButton.hidden = !renderer || !wide.matches || reduced.matches;
    motionButton.textContent = paused ? "Resume motion" : "Pause motion";
    motionButton.setAttribute("aria-pressed", String(paused));
  }

  async function ensureScene() {
    if (renderer || loading || !onScreen()) return;
    loading = true;
    try {
      const THREE = await import("./vendor/three.module.min.js");
      if (!onScreen()) return;
      canvas = document.createElement("canvas");
      canvas.setAttribute("aria-hidden", "true");
      stage.appendChild(canvas);
      renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: "low-power" });
      renderer.setClearColor(0x000000, 0);
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 1.5;
      renderer.shadowMap.enabled = true;
      renderer.shadowMap.type = THREE.PCFSoftShadowMap;
      scene = new THREE.Scene();
      camera = new THREE.PerspectiveCamera(35, 1, 0.1, 30);
      camera.position.set(0, 0.55, 5.5);
      camera.lookAt(0, 0.1, 0);

      // A folded sheet, not a solid polyhedron. Each triangle has its own
      // normal; the front ridge and recessed lower folds are actual depth.
      const geometry = new THREE.BufferGeometry();
      foldGeometry = geometry;
      geometry.setAttribute("position", new THREE.BufferAttribute(foldPositions(foldProgress), 3));
      geometry.computeVertexNormals();
      FOLD_FACES.forEach((_, i) => geometry.addGroup(i * 3, 3, i >= 4 ? 3 : i % 3));
      const materials = [0xfdf9ef, 0xf4ead8, 0xefe3cd, 0xb3212e].map(color => new THREE.MeshStandardMaterial({
        color, roughness: 0.88, metalness: 0, flatShading: true, side: THREE.DoubleSide,
      }));
      resources.push(geometry, ...materials);
      paper = new THREE.Mesh(geometry, materials);
      paper.castShadow = true;
      paper.receiveShadow = true;
      paper.rotation.set(-0.14 - (1 - foldProgress) * 0.95, targetY + (1 - foldProgress) * 0.7, -0.07);
      paper.position.y = -(1 - foldProgress) * 0.35;
      scene.add(paper);
      scene.add(new THREE.HemisphereLight(0xfff9ed, 0x82735e, 3.0));
      const key = new THREE.DirectionalLight(0xfff5df, 3.8);
      key.position.set(-3.2, 5, 4);
      key.castShadow = true;
      key.shadow.mapSize.set(512, 512);
      key.shadow.camera.left = key.shadow.camera.bottom = -3;
      key.shadow.camera.right = key.shadow.camera.top = 3;
      key.shadow.normalBias = 0.025;
      scene.add(key);
      // Shadow maps allocate a render target lazily; dispose it with the scene.
      resources.push(key.shadow);
      const floorGeometry = new THREE.PlaneGeometry(8, 8);
      const floorMaterial = new THREE.ShadowMaterial({ opacity: 0.07 });
      resources.push(floorGeometry, floorMaterial);
      const floor = new THREE.Mesh(floorGeometry, floorMaterial);
      floor.rotation.x = -Math.PI / 2;
      floor.position.y = -1.3;
      floor.receiveShadow = true;
      scene.add(floor);
      canvas.addEventListener("webglcontextlost", contextLost);
      resize();
      if (renderer) host.classList.add("atlas-rendered");
      controls();
      schedule();
    } catch {
      failed = true;
      release();
    } finally {
      loading = false;
      host.dispatchEvent(new Event("atlas-ready"));
    }
  }

  function reconcile() {
    stop();
    controls();
    if (!wide.matches) {
      release();
      return;
    }
    if (!onScreen()) return;
    if (renderer) {
      if (reduced.matches) {
        progress = 1;
        paper.rotation.set(-0.14, targetY, -0.07);
        paper.position.y = 0;
      }
      resize();
      schedule();
    } else void ensureScene();
  }

  const intersection = new IntersectionObserver(entries => {
    visible = entries[0].isIntersecting;
    reconcile();
  });
  intersection.observe(stage);
  const dimensions = new ResizeObserver(() => {
    resize();
    reconcile();
  });
  dimensions.observe(stage);
  wide.addEventListener("change", reconcile, { signal });
  reduced.addEventListener("change", reconcile, { signal });
  document.addEventListener("visibilitychange", reconcile, { signal });
  window.addEventListener("resize", reconcile, { signal });
  motionButton.addEventListener("click", () => {
    paused = !paused;
    reconcile();
  }, { signal });
  window.addEventListener("pagehide", event => {
    if (event.persisted) { suspended = true; stop(); }
    else dispose();
  }, { signal });
  window.addEventListener("pageshow", () => { suspended = false; reconcile(); }, { signal });

  function update(state) {
    if (disposed) return;
    if (state.fold !== undefined) {
      foldProgress = reduced.matches ? 1 : state.fold;
      if (foldGeometry) {
        const attribute = foldGeometry.getAttribute("position");
        foldPositions(foldProgress, attribute.array);
        attribute.needsUpdate = true;
        foldGeometry.computeVertexNormals();
        const open = 1 - foldProgress;
        paper.rotation.set(-0.14 - open * 0.95, targetY + open * 0.7, -0.07);
        paper.position.y = -open * 0.35;
        draw();
      }
      if (state.available === undefined) {
        if (foldProgress === 1) schedule(); else stop();
        return;
      }
    }
    available = state.available;
    working = state.working;
    if (state.topic !== topic) {
      topic = state.topic;
      let seed = 0;
      for (let i = 0; i < topic.length; i++) seed = (seed * 31 + topic.charCodeAt(i)) | 0;
      startY = paper ? paper.rotation.y : targetY;
      // Topic poses are decorative, not a relationship or file-count encoding.
      targetY = topic ? -0.32 + ((seed >>> 0) % 7 - 3) * 0.12 : -0.32;
      progress = moving() && !state.instant ? 0 : 1;
      if (paper && progress === 1) paper.rotation.y = targetY;
    } else if (working && paper) {
      progress = 1;
      paper.rotation.y = targetY;
      paper.position.y = 0;
    }
    reconcile();
  }

  function dispose() {
    if (disposed) return;
    disposed = true;
    events.abort();
    intersection.disconnect();
    dimensions.disconnect();
    release();
  }

  return { update, dispose };
}
