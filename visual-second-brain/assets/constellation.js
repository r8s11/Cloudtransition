// Three.js r180 and matching OrbitControls are shipped locally under the MIT license.
const GOLDEN_ANGLE = 2.399963229728653;
const compare = (a, b) => a < b ? -1 : a > b ? 1 : 0;
let entranceSeen = false;

/**
 * Decorative coordinates only; membership never comes from position or file metadata.
 * Returns groups {key,label,color,count,x,y,z,radius}, files
 * {path,f,groups:[key],x,y,z,radius}, and edges {path,key,fileIndex,groupIndex}.
 * Arrays are stable by identity, file objects remain original references, and inputs stay untouched.
 */
export function constellationLayout(layout = {}) {
  const groupMap = new Map();
  for (const group of layout.groups || []) {
    if (typeof group?.key !== 'string') continue;
    const candidate = { key: group.key, label: group.label || group.key, color: group.color };
    const previous = groupMap.get(group.key);
    if (!previous || compare(String(candidate.label) + String(candidate.color), String(previous.label) + String(previous.color)) < 0) {
      groupMap.set(group.key, candidate);
    }
  }
  const pathMap = new Map();
  for (const point of layout.files || []) {
    const path = point?.f?.relativePath;
    if (typeof path !== 'string' || !path) continue;
    if (!pathMap.has(path)) pathMap.set(path, { path, f: point.f, memberships: new Set() });
    const file = pathMap.get(path);
    for (const group of point.groups || []) {
      if (groupMap.has(group?.key)) file.memberships.add(group.key);
    }
  }
  const files = [...pathMap.values()].sort((a, b) => compare(a.path, b.path)).map(file => ({
    path: file.path, f: file.f, groups: [...file.memberships].sort(compare), x: 0, y: 0, z: 0, radius: 4.5,
  }));
  const owned = new Map([...groupMap.keys()].map(key => [key, []]));
  const unowned = [];
  const counts = new Map([...groupMap.keys()].map(key => [key, 0]));
  for (const file of files) {
    for (const key of file.groups) counts.set(key, counts.get(key) + 1);
    (file.groups.length ? owned.get(file.groups[0]) : unowned).push(file);
  }
  const groups = [...groupMap.values()].sort((a, b) => owned.get(b.key).length - owned.get(a.key).length || compare(a.key, b.key))
    .map((group, index) => {
      const angle = index * GOLDEN_ANGLE;
      const distance = index ? 170 + Math.sqrt(index) * 65 : 0;
      return { ...group, count: counts.get(group.key), x: Math.cos(angle) * distance * 1.6,
        y: Math.sin(angle) * distance * 0.675, z: Math.sin(index * 1.7) * 195, radius: 9 };
    });
  const place = (members, center) => {
    const radius = 28 + Math.cbrt(members.length) * 20;
    members.forEach((file, index) => {
      const vertical = 1 - 2 * (index + 0.5) / members.length;
      const ring = Math.sqrt(Math.max(0, 1 - vertical * vertical));
      const angle = index * GOLDEN_ANGLE;
      file.x = center.x + Math.cos(angle) * ring * radius * 1.05;
      file.y = center.y + vertical * radius * 0.95;
      file.z = center.z + Math.sin(angle) * ring * radius * 1.15;
    });
  };
  for (const group of groups) place(owned.get(group.key), group);
  place(unowned, { x: 0, y: 0, z: 0 });
  const groupIndices = new Map(groups.map((group, index) => [group.key, index]));
  const edges = [];
  files.forEach((file, fileIndex) => {
    for (const key of file.groups) edges.push({ path: file.path, key, fileIndex, groupIndex: groupIndices.get(key) });
  });
  return { groups, files, edges };
}

export async function createConstellation(host, { layout, dark = true, intro = true, fromPose = null, onPick, onZoom, onFailure } = {}) {
  if (!host?.isConnected) throw new Error('Constellation host is no longer connected');
  const [THREE, { OrbitControls }] = await Promise.all([
    import('./vendor/three.module.min.js'), import('./vendor/OrbitControls.js'),
  ]);
  if (!host.isConnected) throw new Error('Constellation host was removed while loading');
  const allowEntrance = intro && !entranceSeen;
  entranceSeen = true;

  const data = constellationLayout(layout);
  const doc = host.ownerDocument;
  const win = doc.defaultView;
  const events = new AbortController();
  const { signal } = events;
  const resources = [];
  let renderer, scene, camera, controls, canvas, labels, dimensions, intersection;
  let filesMesh, hubsMesh, ringsMesh, lines, selectedLines, selectedGeometry;
  let disposed = false, failed = false, initializing = true, suspended = false, visible = false;
  let width = 0, height = 0, raf = 0, dirty = true, labelSizesDirty = true;
  let fitDistance = 1000, lastZoom = NaN, fitted = true, changingCamera = false, controlsRoot, flyRaf = 0;
  let selectedIndex = -1, hoverIndex = -1, hoverGroupIndex = -1, focused = null, labelNode = null;
  let pendingHover = false, hoverX = 0, hoverY = 0, press = null, initError = null, focusSizeDirty = true;
  const reduced = win.matchMedia('(prefers-reduced-motion: reduce)');
  const entrance = { value: 1 };
  let entrancePending = false, entranceTween = null;
  const pointers = new Set();
  const hubLabels = [];
  const pathIndices = new Map(data.files.map((file, index) => [file.path, index]));
  const keyIndices = new Map(data.groups.map((group, index) => [group.key, index]));
  const matrix = new THREE.Matrix4();
  const point = new THREE.Vector3();
  const direction = new THREE.Vector3();
  const right = new THREE.Vector3();
  const up = new THREE.Vector3();
  const delta = new THREE.Vector3();
  const center = new THREE.Vector3();
  const bounds = new THREE.Box3();
  const marker = new THREE.Object3D();
  const projected = new THREE.Vector3();
  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  const intersections = [];
  const pickMeshes = [];
  const palette = [];
  const nodeColor = new THREE.Color();
  const accent = new THREE.Color();
  const background = new THREE.Color();
  const mutedColor = new THREE.Color();
  const focusRect = { x: 0, y: 0, w: 44, h: 44, visible: false };
  let focusLabel, worldRadius = 100;

  function stop() {
    if (raf) win.cancelAnimationFrame(raf);
    raf = 0;
  }

  function cancelFly() {
    if (flyRaf) { win.cancelAnimationFrame(flyRaf); flyRaf = 0; }
  }

  function finishEntrance() {
    cancelFly();
    entrancePending = false;
    if (!entranceTween) return;
    entranceTween.kill();
    entranceTween = null;
    entrance.value = 1;
    if (!disposed) { updateHighlights(); invalidate(); }
  }

  function startEntrance() {
    entrancePending = false;
    if (reduced.matches || !win.gsap || !onScreen()) return;
    entrance.value = 0;
    updateHighlights();
    entranceTween = win.gsap.to(entrance, {
      value: 1, duration: 0.9, ease: 'power2.out',
      onUpdate() {
        if (disposed) return;
        updateHighlights();
        // GSAP already owns this frame; a second RAF halves the visible cadence.
        stop();
        dirty = true;
        draw();
      },
      onComplete() { entranceTween = null; },
    });
  }

  function destroy() {
    if (disposed) return;
    disposed = true;
    finishEntrance();
    stop();
    events.abort();
    dimensions?.disconnect();
    intersection?.disconnect();
    if (controls) {
      controls.removeEventListener('change', changed);
      // r180 can leave root listeners behind when detached or while Control is held.
      controlsRoot.removeEventListener('keydown', controls._interceptControlDown, { capture: true });
      controlsRoot.removeEventListener('keyup', controls._interceptControlUp, { capture: true });
      controls.dispose();
    }
    pointers.clear();
    for (let index = resources.length - 1; index >= 0; index--) resources[index].dispose();
    resources.length = 0;
    scene?.clear();
    renderer?.dispose();
    canvas?.remove();
    labels?.remove();
    // Remove our loss listener and DOM before intentionally losing the disposed context.
    renderer?.forceContextLoss();
    renderer = scene = camera = controls = null;
  }

  function fail(reason) {
    if (failed || disposed) return;
    failed = true;
    initError = new Error(reason);
    destroy();
    if (!initializing) onFailure?.(reason);
  }

  function onScreen() {
    return !disposed && host.isConnected && !doc.hidden && !suspended && visible && width > 0 && height > 0;
  }

  function schedule() {
    if (!raf && renderer && onScreen() && (dirty || pendingHover)) raf = win.requestAnimationFrame(draw);
  }

  function invalidate() {
    dirty = true;
    schedule();
  }

  function reportZoom() {
    // Perspective OrbitControls dolly: actual magnification at the target, relative to Fit.
    const scale = fitDistance / Math.max(0.001, camera.position.distanceTo(controls.target));
    if (!Number.isFinite(lastZoom) || Math.abs(scale - lastZoom) > 0.0001) {
      lastZoom = scale;
      onZoom?.(scale);
    }
  }

  function changed() {
    if (disposed) return;
    if (!changingCamera) fitted = false;
    const hadHover = hoverIndex !== -1 || hoverGroupIndex !== -1;
    hoverIndex = -1;
    hoverGroupIndex = -1;
    pendingHover = false;
    updateFocusLabel();
    if (hadHover) updateHighlights();
    reportZoom();
    invalidate();
  }

  function fitPose() {
    direction.subVectors(camera.position, controls.target).normalize();
    if (!direction.lengthSq()) direction.set(0, 0.12, 1).normalize();
    camera.updateMatrixWorld();
    right.setFromMatrixColumn(camera.matrixWorld, 0);
    up.setFromMatrixColumn(camera.matrixWorld, 1);
    const tanY = Math.tan(THREE.MathUtils.degToRad(camera.fov * 0.5));
    const tanX = tanY * camera.aspect;
    let distance = 20;
    for (const collection of [data.files, data.groups]) for (const node of collection) {
      delta.set(node.x, node.y, node.z).sub(center);
      const radius = node.radius * 1.75, depth = delta.dot(direction) + radius;
      distance = Math.max(distance, depth + (Math.abs(delta.dot(right)) + radius) / tanX,
        depth + (Math.abs(delta.dot(up)) + radius) / tanY);
    }
    distance *= 1.08;
    return { distance, target: center.clone(), position: center.clone().addScaledVector(direction, distance) };
  }

  function fit(interrupt = true) {
    if (disposed || !width || !height) return;
    if (interrupt) finishEntrance();
    cancelFly();
    const pose = fitPose();
    fitDistance = pose.distance;
    controls.maxDistance = Math.max(pose.distance * 8, worldRadius * 10);
    controls.target.copy(pose.target);
    camera.position.copy(pose.position);
    changingCamera = true;
    controls.update();
    changingCamera = false;
    fitted = true;
    reportZoom();
    invalidate();
  }

  // Overdrive: ease the camera from its current pose into the Fit framing of
  // the (filtered) result set. Interruptible by any user input via cancelFly.
  function flyToFit(duration) {
    if (disposed || !width || !height) return;
    cancelFly();
    const pose = fitPose();
    fitDistance = pose.distance;
    controls.maxDistance = Math.max(pose.distance * 8, worldRadius * 10);
    const fromPos = camera.position.clone(), fromTgt = controls.target.clone();
    const start = performance.now();
    const step = (now) => {
      flyRaf = 0;
      if (disposed) return;
      const t = Math.min(1, (now - start) / duration);
      const e = 1 - Math.pow(1 - t, 3);
      camera.position.lerpVectors(fromPos, pose.position, e);
      controls.target.lerpVectors(fromTgt, pose.target, e);
      changingCamera = true;
      controls.update();
      changingCamera = false;
      reportZoom();
      invalidate();
      if (t < 1) flyRaf = win.requestAnimationFrame(step);
      else fitted = true;
    };
    flyRaf = win.requestAnimationFrame(step);
  }

  function resize() {
    if (disposed) return;
    const nextWidth = host.clientWidth;
    const nextHeight = host.clientHeight;
    const ratio = Math.min(win.devicePixelRatio || 1, 1.5);
    if (nextWidth !== width || nextHeight !== height || ratio !== renderer.getPixelRatio()) {
      if (entranceTween) finishEntrance();
      const first = !width || !height;
      width = nextWidth;
      height = nextHeight;
      labelSizesDirty = true;
      if (!width || !height) { stop(); return; }
      renderer.setPixelRatio(ratio);
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      if (first && nextWidth < 600) {
        camera.position.set(1000, 180, 180);
        camera.lookAt(controls.target);
      }
      if (fitted) fit(false);
      invalidate();
    }
    schedule();
  }

  function resolveColor(style, value, fallback) {
    let resolved = value || fallback;
    for (let depth = 0; depth < 6 && resolved.startsWith('var('); depth++) {
      const match = /^var\(\s*(--[^,\s)]+)(?:,\s*([^)]*))?\s*\)$/.exec(resolved);
      if (!match) return fallback;
      resolved = style.getPropertyValue(match[1]).trim() || match[2]?.trim() || fallback;
    }
    return resolved.startsWith('var(') ? fallback : resolved;
  }

  function theme(nextDark) {
    if (disposed) return;
    if (dark !== nextDark) finishEntrance();
    dark = nextDark;
    const style = win.getComputedStyle(host);
    const fallbackPalette = dark
      ? ['#76b7f4', '#58cbbb', '#db9be0', '#f2be72', '#b3abff', '#ef9a9a']
      : ['#275e9a', '#237767', '#8b3f8f', '#92621b', '#6351a9', '#a73e48'];
    background.setStyle(resolveColor(style, 'var(--paper)', dark ? '#10171f' : '#f8f5ed'));
    nodeColor.setStyle(resolveColor(style, 'var(--graph-node)', dark ? '#b6c8d8' : '#625d54'));
    accent.setStyle(resolveColor(style, 'var(--graph-accent)', dark ? '#ff8d98' : '#b3212e'));
    renderer.setClearColor(background, 1);
    data.groups.forEach((group, index) => {
      let slot = 0;
      for (const char of group.key) slot = (slot + char.codePointAt(0)) % 6;
      const css = resolveColor(style, group.color || `var(--graph-c${slot + 1})`, fallbackPalette[slot]);
      (palette[index] ||= new THREE.Color()).setStyle(css);
      hubsMesh.setColorAt(index, palette[index]);
      hubLabels[index].element.style.borderLeftColor = css;
      ringsMesh.setColorAt(index, palette[index]);
    });
    if (hubsMesh.instanceColor) hubsMesh.instanceColor.needsUpdate = true;
    if (ringsMesh.instanceColor) ringsMesh.instanceColor.needsUpdate = true;
    const colors = lines.geometry.getAttribute('color');
    data.edges.forEach((edge, index) => {
      const color = palette[edge.groupIndex];
      colors.setXYZ(index * 2, color.r, color.g, color.b);
      colors.setXYZ(index * 2 + 1, color.r, color.g, color.b);
    });
    colors.needsUpdate = true;
    selectedLines.material.color.copy(accent);
    labels.style.color = resolveColor(style, 'var(--ink)', dark ? '#f0ede6' : '#26231e');
    const labelBackground = resolveColor(style, 'var(--paper-hi)', dark ? '#141e29' : '#fffdf8');
    for (const label of hubLabels) {
      label.element.style.background = labelBackground;
      label.element.style.color = labels.style.color;
    }
    focusLabel.style.background = labelBackground;
    focusLabel.style.borderColor = resolveColor(style, 'var(--graph-accent)', dark ? '#ff8d98' : '#b3212e');
    updateHighlights();
    labelSizesDirty = true;
    invalidate();
  }

  function updateHighlights() {
    const focusedFileIndex = focused?.type === 'file' ? pathIndices.get(focused.path) : -1;
    const focusedGroupIndex = focused?.type === 'group' ? keyIndices.get(focused.key) : -1;
    const hasFocus = Boolean(focused);
    const activeFileIndex = focusedFileIndex >= 0 ? focusedFileIndex
      : !hasFocus && selectedIndex >= 0 ? selectedIndex
        : !hasFocus && selectedIndex < 0 ? hoverIndex : -1;
    const activeGroupIndex = focusedGroupIndex >= 0 ? focusedGroupIndex
      : !hasFocus && selectedIndex < 0 && activeFileIndex < 0 ? hoverGroupIndex : -1;
    const activeGroupKey = activeGroupIndex >= 0 ? data.groups[activeGroupIndex].key : null;
    const hasActive = activeFileIndex >= 0 || activeGroupIndex >= 0;
    data.files.forEach((file, index) => {
      const highlighted = index === activeFileIndex
        || activeGroupIndex >= 0 && file.groups.includes(activeGroupKey);
      const groupIndex = keyIndices.get(file.groups[0]);
      const phase = Math.min(1, Math.max(0, entrance.value * 1.2 - (groupIndex || 0) / Math.max(1, data.groups.length - 1) * 0.2));
      const scale = (0.7 + 0.3 * phase) * (highlighted ? 1.75 : 1);
      matrix.makeScale(scale, scale, scale);
      matrix.setPosition(file.x, file.y, file.z);
      filesMesh.setMatrixAt(index, matrix);
      mutedColor.copy(palette[groupIndex] || nodeColor);
      if (hasActive && !highlighted) mutedColor.lerp(background, 0.68);
      filesMesh.setColorAt(index, highlighted ? accent : mutedColor);
    });
    filesMesh.instanceMatrix.needsUpdate = true;
    if (filesMesh.instanceColor) filesMesh.instanceColor.needsUpdate = true;
    data.groups.forEach((group, index) => {
      const related = activeFileIndex >= 0 ? data.files[activeFileIndex].groups.includes(group.key)
        : index === activeGroupIndex;
      mutedColor.copy(palette[index] || nodeColor);
      if (hasActive && !related) mutedColor.lerp(background, 0.68);
      hubsMesh.setColorAt(index, related ? accent : mutedColor);
      marker.position.set(group.x, group.y, group.z);
      marker.rotation.set(0, 0, 0);
      marker.scale.setScalar((related ? 1.12 : 0.85) + 0.15 * entrance.value);
      marker.updateMatrix();
      hubsMesh.setMatrixAt(index, marker.matrix);
      ringsMesh.setColorAt(index, related ? accent : mutedColor);
      marker.rotation.set(0.5, index * 0.28, 0.15);
      marker.scale.setScalar((related ? 0.9 : 0.7) + 0.3 * entrance.value);
      marker.updateMatrix();
      ringsMesh.setMatrixAt(index, marker.matrix);
    });
    hubsMesh.instanceMatrix.needsUpdate = true;
    ringsMesh.instanceMatrix.needsUpdate = true;
    if (hubsMesh.instanceColor) hubsMesh.instanceColor.needsUpdate = true;
    if (ringsMesh.instanceColor) ringsMesh.instanceColor.needsUpdate = true;
    const positions = selectedGeometry.getAttribute('position');
    const source = lines.geometry.getAttribute('position');
    let count = 0;
    data.edges.forEach((edge, index) => {
      // Nothing hovered/focused/selected: no accent overlay, membership colours show.
      if (!hasActive || (activeFileIndex >= 0 ? edge.fileIndex !== activeFileIndex
        : edge.groupIndex !== activeGroupIndex)) return;
      positions.array.set(source.array.subarray(index * 6, index * 6 + 6), count * 6);
      count++;
    });
    positions.needsUpdate = true;
    selectedGeometry.setDrawRange(0, count * 2);
    selectedLines.material.opacity = activeGroupIndex >= 0 ? 0.28 : 0.85;
    lines.material.opacity = (hasActive ? 0.055 : dark ? 0.15 : 0.19) * (0.6 + 0.4 * entrance.value);
  }

  function currentLabelNode() {
    if (focused?.type === 'group') return data.groups[keyIndices.get(focused.key)];
    if (focused?.type === 'file') return data.files[pathIndices.get(focused.path)];
    if (selectedIndex >= 0) return data.files[selectedIndex];
    if (hoverIndex >= 0) return data.files[hoverIndex];
    return data.groups[hoverGroupIndex];
  }

  function updateFocusLabel() {
    const next = currentLabelNode();
    if (next !== labelNode) {
      labelNode = next;
      focusLabel.textContent = next ? next.path ? next.f.name || next.path : `${next.label} · ${next.count}` : '';
      focusLabel.title = next?.path || next?.label || '';
      focusSizeDirty = true;
    }
    focusLabel.style.pointerEvents = focused || selectedIndex >= 0 ? 'auto' : 'none';
    const borderWidth = focused ? '2px' : '1px';
    if (focusLabel.style.borderWidth !== borderWidth) focusSizeDirty = true;
    focusLabel.style.borderWidth = borderWidth;
  }

  function measureLabel(element, rect) {
    element.hidden = false;
    element.style.visibility = 'hidden';
    element.style.maxWidth = `${Math.max(44, Math.min(260, width - 24))}px`;
    rect.w = element.offsetWidth;
    rect.h = element.offsetHeight;
    element.style.visibility = '';
    element.hidden = true;
  }

  function overlaps(a, b) {
    return b.visible && a.x < b.x + b.w + 8 && a.x + a.w + 8 > b.x
      && a.y < b.y + b.h + 8 && a.y + a.h + 8 > b.y;
  }

  function positionLabels() {
    if (labelSizesDirty) {
      for (const label of hubLabels) measureLabel(label.element, label);
    }
    if (labelSizesDirty || focusSizeDirty) measureLabel(focusLabel, focusRect);
    labelSizesDirty = focusSizeDirty = false;
    focusRect.visible = Boolean(labelNode);
    if (labelNode) {
      projected.set(labelNode.x, labelNode.y, labelNode.z).project(camera);
      const x = (projected.x + 1) * width * 0.5 + 12;
      const y = (1 - projected.y) * height * 0.5 - focusRect.h * 0.5;
      focusRect.x = Math.max(8, Math.min(width - focusRect.w - 8, Number.isFinite(x) ? x : 8));
      focusRect.y = Math.max(8, Math.min(height - focusRect.h - 8, Number.isFinite(y) ? y : 8));
      focusLabel.dataset.proxy = String(projected.z < -1 || projected.z > 1 || x !== focusRect.x || y !== focusRect.y);
      focusLabel.style.transform = `translate(${Math.round(focusRect.x)}px,${Math.round(focusRect.y)}px)`;
    }
    focusLabel.hidden = !focusRect.visible;
    let shown = 0;
    for (let index = 0; index < hubLabels.length; index++) {
      const label = hubLabels[index];
      const group = data.groups[index];
      projected.set(group.x, group.y, group.z).project(camera);
      label.x = (projected.x + 1) * width * 0.5 + 10;
      label.y = (1 - projected.y) * height * 0.5 - label.h * 0.5;
      label.visible = projected.z >= -1 && projected.z <= 1 && label.x >= 8 && label.y >= 8
        && label.x + label.w <= width - 8 && label.y + label.h <= height - 8
        && shown < (width < 600 ? 4 : 12) && !overlaps(label, focusRect);
      for (let previous = 0; label.visible && previous < index; previous++) {
        if (overlaps(label, hubLabels[previous])) label.visible = false;
      }
      label.element.hidden = !label.visible;
      if (label.visible) {
        label.element.style.transform = `translate(${Math.round(label.x)}px,${Math.round(label.y)}px)`;
        shown++;
      }
    }
  }

  function hitAt(x, y) {
    const rect = canvas.getBoundingClientRect();
    if (!rect.width || !rect.height) return null;
    pointer.set((x - rect.left) / rect.width * 2 - 1, 1 - (y - rect.top) / rect.height * 2);
    camera.updateMatrixWorld();
    scene.updateMatrixWorld();
    raycaster.setFromCamera(pointer, camera);
    intersections.length = 0;
    raycaster.intersectObjects(pickMeshes, false, intersections);
    return intersections[0] || null;
  }

  function draw() {
    raf = 0;
    if (!onScreen()) return;
    try {
      if (entrancePending) startEntrance();
      if (pendingHover) {
        pendingHover = false;
        const hit = hitAt(hoverX, hoverY);
        const index = hit?.object === filesMesh ? hit.instanceId : -1;
        const groupIndex = hit?.object === hubsMesh ? hit.instanceId : -1;
        canvas.style.cursor = hit ? 'pointer' : 'grab';
        if (index !== hoverIndex || groupIndex !== hoverGroupIndex) {
          hoverIndex = index;
          hoverGroupIndex = groupIndex;
          updateFocusLabel();
          updateHighlights();
          dirty = true;
        }
      }
      if (!dirty) return;
      dirty = false;
      renderer.render(scene, camera);
      positionLabels();
    } catch {
      fail('3D rendering failed; use the 2D graph');
    }
  }

  function pick(entry) {
    // Let OrbitControls finish its pointerup before a parent action replaces this view.
    queueMicrotask(() => { if (!disposed) onPick?.(entry); });
  }

  function makeLabel(text) {
    const element = doc.createElement('button');
    element.type = 'button';
    element.tabIndex = -1;
    element.setAttribute('aria-hidden', 'true');
    element.textContent = text;
    element.hidden = true;
    Object.assign(element.style, {
      position: 'absolute', top: '0', left: '0', minWidth: '44px', minHeight: '44px',
      boxSizing: 'border-box', padding: '8px 12px', border: '1px solid', borderRadius: '4px',
      color: 'inherit', fontFamily: 'inherit', fontSize: '12px', fontWeight: '600', lineHeight: '1.2',
      textAlign: 'left', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
      pointerEvents: 'auto', cursor: 'pointer', touchAction: 'manipulation',
    });
    element.addEventListener('pointerdown', event => { event.preventDefault(); event.stopPropagation(); }, { signal });
    labels.appendChild(element);
    return element;
  }

  try {
    canvas = doc.createElement('canvas');
    canvas.tabIndex = -1;
    canvas.setAttribute('aria-hidden', 'true');
    canvas.className = 'constellation-canvas';
    Object.assign(canvas.style, { position: 'absolute', inset: '0', width: '100%', height: '100%', display: 'block', cursor: 'grab' });
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false, powerPreference: 'low-power' });
    canvas.addEventListener('webglcontextlost', event => {
      event.preventDefault();
      fail('WebGL context lost; use the 2D graph');
    }, { signal });
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.2;
    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(42, 1, 0.1, 6000);
    camera.position.set(0, 120, 1000);
    const hemisphere = new THREE.HemisphereLight(0xd8e8ff, 0x514331, 2.2);
    const key = new THREE.DirectionalLight(0xfff0d6, 2.8);
    key.position.set(-450, 650, 800);
    const rim = new THREE.DirectionalLight(0x9fc9ff, 1.8);
    rim.position.set(650, 100, -650);
    scene.add(hemisphere, key, rim);

    const geometry = new THREE.SphereGeometry(4.5, 16, 10);
    const material = new THREE.MeshStandardMaterial({ roughness: 0.48, metalness: 0.04 });
    resources.push(geometry, material);
    filesMesh = new THREE.InstancedMesh(geometry, material, data.files.length);
    resources.push(filesMesh);
    const hubGeometry = new THREE.SphereGeometry(9, 24, 16);
    const hubMaterial = new THREE.MeshStandardMaterial({ roughness: 0.42, metalness: 0.04 });
    resources.push(hubGeometry, hubMaterial);
    hubsMesh = new THREE.InstancedMesh(hubGeometry, hubMaterial, data.groups.length);
    resources.push(hubsMesh);
    data.groups.forEach((group, index) => {
      matrix.makeTranslation(group.x, group.y, group.z);
      hubsMesh.setMatrixAt(index, matrix);
    });
    hubsMesh.instanceMatrix.needsUpdate = true;
    const ringGeometry = new THREE.TorusGeometry(12.5, 0.5, 6, 32);
    const ringMaterial = new THREE.MeshStandardMaterial({ roughness: 0.55, metalness: 0 });
    ringsMesh = new THREE.InstancedMesh(ringGeometry, ringMaterial, data.groups.length);
    resources.push(ringGeometry, ringMaterial, ringsMesh);
    const edgePositions = new Float32Array(data.edges.length * 6);
    data.edges.forEach((edge, index) => {
      const file = data.files[edge.fileIndex];
      const group = data.groups[edge.groupIndex];
      edgePositions.set([file.x, file.y, file.z, group.x, group.y, group.z], index * 6);
    });
    const edgeGeometry = new THREE.BufferGeometry();
    edgeGeometry.setAttribute('position', new THREE.BufferAttribute(edgePositions, 3));
    edgeGeometry.setAttribute('color', new THREE.BufferAttribute(new Float32Array(edgePositions.length), 3));
    const edgeMaterial = new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.2, depthWrite: false });
    resources.push(edgeGeometry, edgeMaterial);
    lines = new THREE.LineSegments(edgeGeometry, edgeMaterial);
    selectedGeometry = new THREE.BufferGeometry();
    selectedGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(edgePositions.length), 3));
    selectedGeometry.setDrawRange(0, 0);
    const selectedMaterial = new THREE.LineBasicMaterial({ transparent: true, opacity: 0.85, depthWrite: false });
    resources.push(selectedGeometry, selectedMaterial);
    selectedLines = new THREE.LineSegments(selectedGeometry, selectedMaterial);
    selectedLines.frustumCulled = false;
    scene.add(lines, selectedLines, filesMesh, hubsMesh, ringsMesh);
    pickMeshes.push(filesMesh, hubsMesh);

    for (const node of [...data.files, ...data.groups]) {
      const radius = node.radius * 1.75;
      point.set(node.x - radius, node.y - radius, node.z - radius);
      bounds.expandByPoint(point);
      point.set(node.x + radius, node.y + radius, node.z + radius);
      bounds.expandByPoint(point);
    }
    if (bounds.isEmpty()) bounds.set(new THREE.Vector3(-20, -20, -20), new THREE.Vector3(20, 20, 20));
    bounds.getCenter(center);
    bounds.getSize(point);
    worldRadius = Math.max(20, point.length() * 0.5);
    camera.far = Math.max(6000, worldRadius * 60);
    camera.updateProjectionMatrix();
    labels = doc.createElement('div');
    labels.className = 'constellation-labels';
    labels.tabIndex = -1;
    labels.setAttribute('aria-hidden', 'true');
    Object.assign(labels.style, { position: 'absolute', inset: '0', overflow: 'hidden', pointerEvents: 'none', fontFamily: 'inherit' });
    for (const group of data.groups) {
      const element = makeLabel(group.label);
      const count = doc.createElement('span');
      count.textContent = group.count;
      Object.assign(count.style, { fontFamily: 'var(--mono, monospace)', fontSize: '11px', fontWeight: '400', marginLeft: '9px', color: 'var(--ink-mid)' });
      element.appendChild(count);
      Object.assign(element.style, { border: '0', borderLeft: '2px solid', borderRadius: '0', fontSize: '13px', fontWeight: '550', padding: '6px 10px' });
      element.title = group.label;
      element.addEventListener('click', () => pick({ type: 'group', key: group.key }), { signal });
      hubLabels.push({ element, x: 0, y: 0, w: 44, h: 44, visible: false });
    }
    focusLabel = makeLabel('');
    focusLabel.style.zIndex = '1';
    focusLabel.addEventListener('click', () => {
      if (labelNode) pick(labelNode.path ? { type: 'file', path: labelNode.path } : { type: 'group', key: labelNode.key });
    }, { signal });
    if (!host.isConnected) throw new Error('Constellation host was removed while initializing');
    host.append(canvas, labels);
    controlsRoot = canvas.getRootNode();
    controls = new OrbitControls(camera, canvas);
    controls.enableDamping = false;
    controls.autoRotate = false;
    controls.minDistance = Math.max(12, worldRadius * 0.015);
    controls.addEventListener('change', changed);
    theme(dark);
    filesMesh.computeBoundingSphere();
    hubsMesh.computeBoundingSphere();
    ringsMesh.computeBoundingSphere();
    // Include the selected/focused instance scale without rebuilding bounds on every selection.
    if (filesMesh.boundingSphere) filesMesh.boundingSphere.radius += 4;
    renderer.compile(scene, camera);

    canvas.addEventListener('pointerdown', event => {
      finishEntrance();
      pointers.add(event.pointerId);
      if (pointers.size === 1 && event.button === 0) press = { id: event.pointerId, x: event.clientX, y: event.clientY, moved: false };
      else if (press) press.moved = true;
      pendingHover = false;
    }, { signal });
    canvas.addEventListener('pointermove', event => {
      if (press && Math.hypot(event.clientX - press.x, event.clientY - press.y) > 6) press.moved = true;
      if (pointers.size || event.pointerType === 'touch' || !onScreen()) return;
      hoverX = event.clientX;
      hoverY = event.clientY;
      pendingHover = true;
      schedule();
    }, { signal });
    canvas.addEventListener('pointerup', event => {
      pointers.delete(event.pointerId);
      const click = press?.id === event.pointerId && !press.moved;
      if (press?.id === event.pointerId) press = null;
      if (!click || !onScreen()) return;
      const hit = hitAt(event.clientX, event.clientY);
      if (!hit || hit.instanceId === undefined) return;
      if (hit.object === filesMesh) pick({ type: 'file', path: data.files[hit.instanceId].path });
      else pick({ type: 'group', key: data.groups[hit.instanceId].key });
    }, { signal });
    canvas.addEventListener('pointercancel', event => {
      pointers.delete(event.pointerId);
      if (press?.id === event.pointerId) press = null;
    }, { signal });
    canvas.addEventListener('pointerleave', () => {
      pendingHover = false;
      if (hoverIndex !== -1 || hoverGroupIndex !== -1) {
        hoverIndex = -1;
        hoverGroupIndex = -1;
        updateFocusLabel();
        updateHighlights();
        invalidate();
      }
    }, { signal });
    doc.addEventListener('pointerdown', finishEntrance, { signal, capture: true });
    doc.addEventListener('keydown', finishEntrance, { signal, capture: true });
    doc.addEventListener('input', finishEntrance, { signal, capture: true });
    canvas.addEventListener('wheel', finishEntrance, { signal, passive: true, capture: true });
    reduced.addEventListener('change', finishEntrance, { signal });
    dimensions = new ResizeObserver(resize);
    dimensions.observe(host);
    intersection = new IntersectionObserver(entries => {
      visible = entries[0].isIntersecting;
      if (visible) { resize(); invalidate(); }
      else { finishEntrance(); stop(); }
    });
    intersection.observe(host);
    doc.addEventListener('visibilitychange', () => {
      controls.enabled = !doc.hidden && !suspended;
      if (doc.hidden) { finishEntrance(); stop(); }
      else { resize(); invalidate(); }
    }, { signal });
    win.addEventListener('resize', () => { finishEntrance(); resize(); }, { signal });
    win.addEventListener('pagehide', event => {
      if (!event.persisted) destroy();
      else { suspended = true; controls.enabled = false; finishEntrance(); stop(); }
    }, { signal });
    win.addEventListener('pageshow', () => {
      suspended = false;
      controls.enabled = !doc.hidden;
      resize();
      invalidate();
    }, { signal });
    if (doc.fonts) {
      const fontChange = () => { if (!disposed) { labelSizesDirty = true; invalidate(); } };
      doc.fonts.addEventListener('loadingdone', fontChange, { signal });
      doc.fonts.ready.then(fontChange);
    }
    resize();
    reportZoom();
    // Overdrive: a search/filter rebuild flies in from the previous camera pose.
    if (fromPose && !reduced.matches && Array.isArray(fromPose.position) && Array.isArray(fromPose.target)) {
      camera.position.fromArray(fromPose.position);
      controls.target.fromArray(fromPose.target);
      changingCamera = true;
      controls.update();
      changingCamera = false;
      fitted = false;
      flyToFit(700);
    }
    if (!host.isConnected) throw new Error('Constellation host was removed during initialization');
    if (renderer.getContext().isContextLost()) throw new Error('WebGL context was lost during initialization');
    if (disposed) throw initError || new Error('Constellation was disposed during initialization');
    initializing = false;
    entrancePending = allowEntrance && !reduced.matches && Boolean(win.gsap);
    return {
      select(path) {
        if (disposed) return;
        if ((pathIndices.get(path) ?? -1) !== selectedIndex) finishEntrance();
        selectedIndex = pathIndices.get(path) ?? -1;
        if (path === null) focused = null;
        updateHighlights();
        updateFocusLabel();
        invalidate();
      },
      focus(entry) {
        if (disposed || !entry) return;
        finishEntrance();
        cancelFly();
        const node = entry.type === 'file' ? data.files[pathIndices.get(entry.path)]
          : entry.type === 'group' ? data.groups[keyIndices.get(entry.key)] : null;
        if (!node) return;
        focused = entry.type === 'file' ? { type: 'file', path: node.path } : { type: 'group', key: node.key };
        delta.set(node.x, node.y, node.z).sub(controls.target);
        camera.position.add(delta);
        controls.target.set(node.x, node.y, node.z);
        changingCamera = true;
        controls.update();
        changingCamera = false;
        fitted = false;
        updateHighlights();
        updateFocusLabel();
        invalidate();
      },
      zoom(factor) {
        if (disposed || !Number.isFinite(factor) || factor <= 0) return;
      finishEntrance();
      cancelFly();
        direction.subVectors(camera.position, controls.target);
        const distance = Math.max(controls.minDistance, Math.min(controls.maxDistance, direction.length() / factor));
        direction.setLength(distance);
        camera.position.copy(controls.target).add(direction);
        controls.update();
        fitted = false;
        reportZoom();
        invalidate();
      },
      hubPoint(key) {
        if (disposed || !width || !height || host.clientWidth !== width || host.clientHeight !== height) return null;
        const group = data.groups[keyIndices.get(key)];
        if (!group) return null;
        camera.updateMatrixWorld();
        projected.set(group.x, group.y, group.z).project(camera);
        if (projected.z < -1 || projected.z > 1) return null;
        const rect = host.getBoundingClientRect();
        return {
          x: rect.left + (projected.x + 1) * width / 2,
          y: rect.top + (1 - projected.y) * height / 2,
          color: hubLabels[keyIndices.get(key)].element.style.color,
        };
      },
      fit,
      flyToFit,
      pose() {
        return disposed ? null : { position: camera.position.toArray(), target: controls.target.toArray() };
      },
      theme,
      destroy,
    };
  } catch (error) {
    destroy();
    throw error;
  }
}
