# Spatial FUI Reticle & Volumetric Glass Interface — Technical Documentation

**File:** `index.html`  
**Runtime Architecture:** Zero-Build ES Module Web Application (HTML5 / CSS 3D / Three.js `0.170.0` / GSAP `3.12.5` / Web Audio API)  
**Companion Specification:** `design.md`

---

## 1. System Overview & Architectural Philosophy

The **Spatial FUI Reticle & Volumetric Glass Interface** is a self-contained spatial web application that translates cinema-grade 2.5D/3D Fantasy User Interface (FUI) grammar and Transparent OLED (T-OLED) optical physics into an interactive browser instrument.

Rather than rendering text and UI controls inside a monolithic WebGL canvas—which degrades subpixel font sharpness, accessibility, and pointer responsiveness—the application uses a **hybrid multi-layer architecture**:

1. **WebGL Three.js Layer (`z-index: 1`):** Renders floating volumetric glass enclosures, polar Signed Distance Field (SDF) scanner shaders, instanced 3D radial ticks, selective High Dynamic Range (HDR) bloom, and an interactive 14-node / 22-edge 3D telemetry graph.
2. **Projected SVG & HTML Callout Layer (`z-index: 5`–`6`):** Projects 3D world-space anchor points from rotating reticle brackets into 2D viewport coordinates every frame to drive vector leader polylines and clickable telemetry pills.
3. **CSS 3D Volumetric Window Stage (`z-index: 8`):** Hosts three angled, perspective-transformed glass panels (`WIN_01`, `WIN_02`, `WIN_03`) displaying procedural high-DPI canvas visualizations and live tabular readouts.
4. **Perimeter HUD & Topology Command Layer (`z-index: 14`–`40`):** Provides real-time node search, role filtering, uniform telemetry readouts, and state/dock controls.

### Zero-Build Dependency Resolution

All external libraries load natively via an inline `<script type="importmap">` pointing to ES module CDN endpoints:

| Module Specifier | Resolved Package | Role in Application |
| :--- | :--- | :--- |
| `three` | `three@0.170.0` | Core WebGL scene graph, materials, raycasting, and math primitives |
| `three/addons/` | `three@0.170.0/examples/jsm/` | `OrbitControls`, `EffectComposer`, `RenderPass`, `UnrealBloomPass`, `OutputPass` |
| `gsap` | `gsap@3.12.5` | Cancellable ballistic state timelines, detent snapping, and window deployment choreography |

---

## 2. Multi-Layer Z-Stacking & Coordinate Synchronization

### 2.1 DOM Stacking Context (`z-index` Hierarchy)

Pointer pass-through is strictly managed so users can orbit the 3D scene freely while interacting seamlessly with floating overlays:

| Layer ID / Selector | `z-index` | `pointer-events` | Blend / Transform Mode | Responsibility |
| :--- | :--- | :--- | :--- | :--- |
| `#canvas-container` | `1` | `auto` (`touch-action: none`) | Standard WebGL framebuffer | 3D camera orbit, zoom, and 3D graph node raycasting |
| `#callout-svg` | `5` | `none` | `mix-blend-mode: plus-lighter` | Real-time 3D-to-2D projected anchor rings and elbow polylines |
| `#callout-pills` | `6` | `none` (container) / `auto` (`.callout-pill`) | Hardware-accelerated `translate3d` | Interactive telemetry pills pinned to SVG shelf endpoints |
| `#spatial-window-stage` | `8` | `none` (stage) / `auto` (`.is-open`) | `perspective: 1400px`, `preserve-3d` | 2.5D angled volumetric glass windows (`WIN_01`–`WIN_03`) |
| `#graph-inspector` | `14` | `none` | `translate3d` viewport-clamped | Floating 3D-projected metadata card for hovered/pinned graph nodes |
| `.hud-layer` | `15` | `none` (wrapper) / `auto` (docks/bars) | `backdrop-filter: blur(12px)` | Top status cards, `#topology-bar` (`z: 20`), dropdown (`z: 40`), bottom docks |

### 2.2 Synchronized 2.5D Pointer Parallax

Moving the pointer across the viewport drives both the Three.js `reticleRig` rotation and the CSS 3D `.window-rig` tilt from a single normalized pointer vector $(n_x, n_y) \in [-1, 1]^2$:

$$
n_x = \frac{2 x_{\text{client}}}{W} - 1, \qquad n_y = \frac{2 y_{\text{client}}}{H} - 1
$$

* **Three.js Rig:** Smoothly damps `reticleRig.rotation.x` and `reticleRig.rotation.y` toward $(-n_y \cdot 7.5^\circ,\; n_x \cdot 7.5^\circ)$ with an exponential smoothing factor of $0.08$ per frame.
* **CSS 3D Window Stage:** Updates `--stage-tilt-x` and `--stage-tilt-y` within $\pm 5.5^\circ$ so foreground CSS glass windows tilt in unison with the underlying WebGL geometry.

---

## 3. Selective HDR Rendering Pipeline & Shader Engineering

### 3.1 `HalfFloatType` Bloom Pipeline (`createFuiComposer`)

Standard 8-bit render targets clamp RGB values to $[0.0, 1.0]$, causing `UnrealBloomPass` to wash out fine hairlines and translucent glass surfaces. `createFuiComposer` avoids this by configuring an HDR post-processing chain:

1. **HDR MSAA Render Target:** Allocates a `THREE.WebGLRenderTarget` with `type: THREE.HalfFloatType` and `samples: 4` ($4\times$ hardware multisampling).
2. **`RenderPass`:** Renders the scene onto the `#04070d` optical void substrate.
3. **`UnrealBloomPass`:** Configured with **`threshold = 1.05`**. Because Standard Dynamic Range (SDR) white peaks at $1.0$, any material with linear RGB intensity below $1.05$ bypasses bloom completely, whereas materials with `toneMapped: false` and linear RGB multipliers $> 1.05$ emit a controlled cinematic glow.
4. **`OutputPass`:** Applies `THREE.ACESFilmicToneMapping` (`toneMappingExposure = 1.0`) and converts linear HDR values to display sRGB.

### 3.2 Luminance Budget Allocation

| Visual Element | Linear RGB Multiplier | `toneMapped` | Post-Processing Behavior |
| :--- | :--- | :--- | :--- |
| Background Spatial Crosshairs | $0.28$ | `false` | Sub-bloom SDR; subtle spatial depth reference |
| Volumetric Glass Interior | $0.14$ | `false` | Sub-bloom SDR; preserves see-through clarity |
| Polar SDF Outer & Mid Rings | $0.48$–$0.82$ | `false` | Sub-bloom SDR; razor-sharp anti-aliased hairlines |
| Minor Radial Ticks (60 of 72) | $0.78$ | `false` | Sub-bloom SDR; crisp graduated scale |
| Major Cardinal Ticks (12 of 72) | $2.20$ | `false` | Exceeds $1.05$; triggers selective HDR bloom |
| Polar SDF Inner Core & Sweep Lead | $1.30$–$3.36$ (`uHdrGain`) | `false` | Dynamic HDR bloom scaled by operational state |
| Foreground Arc Lock Brackets | $1.45$–$3.10$ | `false` | High-luminance focal bloom |
| Active / Incident Graph Edges & Packets | $1.65$–$3.40$ | `false` | Selective bloom along active topology paths |

### 3.3 Custom GLSL Shaders

#### Polar SDF Scanner Shader (`createPolarReticleDisc`)

Instead of high-poly ring meshes, a single quad evaluates radial distance $r = \|\mathbf{v}_{uv}\|$ and normalized polar angle $\hat{\theta} = \frac{\text{atan2}(v_y, v_x) + \pi}{2\pi} \in [0, 1]$ per pixel. Ring edges use screen-space partial derivatives (`fwidth`) for resolution-independent anti-aliasing:

$$
\text{sdfRing}(r, r_0, w) = 1 - \text{smoothstep}\!\left(-a,\; a,\; |r - r_0| - w\right), \qquad a = 1.15 \cdot \text{fwidth}(|r - r_0| - w)
$$

A rotating radar sweep wedge computes phase $\phi = \text{fract}\!\left(\hat{\theta} - t \cdot \frac{u_{\text{ScanSpeed}}}{2\pi}\right)$, combining a sixth-power exponential tail ($\phi^6$) with a leading-edge HDR spike ($\phi \in [0.985, 1.0]$).

#### Double-Sided Volumetric Glass Shader (`createVolumetricGlassEnclosure`)

Applied to a `THREE.BoxGeometry(5.1, 3.6, 0.07)` with `THREE.DoubleSide` and `THREE.AdditiveBlending` to solve the cinematic **"Back-of-the-UI"** problem when orbiting $360^\circ$:

* **Normal Inversion:** Flips `normalWS = -normalWS` whenever `!gl_FrontFacing` so reverse-side grazing angles illuminate identically to the front.
* **Schlick Fresnel Rim:** Highlights glass thickness along oblique angles via:
  $$
  F = \left(1 - \text{clamp}(\mathbf{N} \cdot \mathbf{V},\; 0,\; 1)\right)^{2.8}
  $$
* **Micro-Voxel Lattice & Rear Attenuation:** Modulates interior tint with animated vertical scanlines ($\sin(160 v_y - 1.4 t)$) and scales reverse-face emission by `uRearDimming = 0.65` so front-facing telemetry retains visual priority.

---

## 4. 3D Scene Graph & Stratified Z-Planes

All 3D reticle components and graph layers are parented to `reticleRig` (`THREE.Group`) across six discrete Z-strata:

| Stratum | Z-Coordinate | Builder / Class | Geometry & Rendering Details |
| :--- | :--- | :--- | :--- |
| **Plane 1** | $Z = -0.85$ | `createBackgroundSpatialGrid()` | `THREE.LineSegments` crosshair lattice spanning $[-3.2, +3.2]$ at $0.4$ intervals ($1.2 \le r \le 3.1$). |
| **Plane 2** | $Z = -0.35$ | `createPolarReticleDisc(2.15)` | `PlaneGeometry(4.3, 4.3)` driven by the Polar SDF Scanner fragment shader. |
| **Plane 3** | $Z = -0.14$ | `createVolumetricGlassEnclosure()` | `BoxGeometry(5.1, 3.6, 0.07)` rendered with double-sided Fresnel bevel glass shader. |
| **Plane 4** | $Z = 0.00$ | `createInstancedRadialTicks(72, 1.56)` | Single-draw-call `THREE.InstancedMesh` of 72 radial bars with per-instance HDR color multipliers. |
| **Graph Volume** | $Z \in [-0.45, +0.32]$ | `SpatialGraphSystem` | 14 polyhedral nodes, 22 weighted edges, 44 signal packets, and diamond lock reticle. |
| **Plane 5** | $Z \in [+0.16, +0.42]$ | `createForegroundLockBrackets(0.94)` | Three $52^\circ$ indexed ribbon arc brackets at $0^\circ, 120^\circ, 240^\circ$ with inner pips and 3 SVG projection anchors. |
| **Plane 6** | $Z = +0.48$ | `createCenterCore()` | Precision focal ring ($r \in [0.14, 0.155]$), center dot, and 4 orthogonal crosshair segments. |

---

## 5. Interactive 3D Graph Topology (`SpatialGraphSystem`)

`SpatialGraphSystem` embeds an interactive 3D network graph directly inside the reticle volume, linking spatial nodes to the 2.5D volumetric glass windows.

### 5.1 Node & Edge Topology Schema

The network comprises **14 nodes** across three functional roles (**3 Hubs**, **6 Sensors**, **5 Compute**), including a **3-node fault path** (`THERM_ARR`, `PWR_CELL`, `SPECTRA_IO`), connected by **22 weighted edges** ($w \in [0.65, 0.95]$):

| Node ID | Role | 3D Coordinates $(x, y, z)$ | Fault Path | Latency | Throughput | Linked Window |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `SYS_CORE` | `HUB` | $(0.00,\; 0.00,\; +0.14)$ | No | `0.4 ms` | `128.0 Gbps` | `WIN_01 [LIDAR]` |
| `NAV_HUB` | `HUB` | $(-0.68,\; +0.46,\; +0.24)$ | No | `0.9 ms` | `84.2 Gbps` | `WIN_02 [RECON]` |
| `OPTIC_AI` | `HUB` | $(+0.72,\; +0.42,\; +0.22)$ | No | `1.1 ms` | `92.6 Gbps` | `WIN_02 [RECON]` |
| `LIDAR_N` | `SENSOR` | $(-1.28,\; +0.86,\; -0.18)$ | No | `1.8 ms` | `42.0 Gbps` | `WIN_01 [LIDAR]` |
| `LIDAR_S` | `SENSOR` | $(-1.34,\; -0.64,\; -0.26)$ | No | `2.1 ms` | `39.5 Gbps` | `WIN_01 [LIDAR]` |
| `BATHY_DSP` | `COMPUTE` | $(-0.78,\; -0.42,\; +0.06)$ | No | `1.4 ms` | `64.8 Gbps` | `WIN_01 [LIDAR]` |
| `APERTURE_L` | `SENSOR` | $(+0.12,\; +1.12,\; -0.12)$ | No | `1.6 ms` | `51.2 Gbps` | `WIN_02 [RECON]` |
| `PHASE_SYNC` | `COMPUTE` | $(+0.06,\; -0.96,\; +0.08)$ | No | `1.2 ms` | `58.4 Gbps` | `WIN_02 [RECON]` |
| `SAR_BEAM` | `SENSOR` | $(+1.26,\; +0.88,\; -0.20)$ | No | `1.9 ms` | `47.1 Gbps` | `WIN_02 [RECON]` |
| `VEC_SOLVER` | `COMPUTE` | $(+1.32,\; -0.12,\; +0.32)$ | No | `1.3 ms` | `71.0 Gbps` | `WIN_02 [RECON]` |
| `GYRO_REF` | `SENSOR` | $(-0.18,\; -1.34,\; -0.45)$ | No | `2.4 ms` | `18.6 Gbps` | `WIN_01 [LIDAR]` |
| `THERM_ARR` | `SENSOR` | $(+0.82,\; -0.58,\; +0.28)$ | **Yes** | `3.8 ms` | `33.4 Gbps` | `WIN_03 [DIAG]` |
| `PWR_CELL` | `COMPUTE` | $(+1.24,\; -0.94,\; -0.14)$ | **Yes** | `4.5 ms` | `29.1 Gbps` | `WIN_03 [DIAG]` |
| `SPECTRA_IO` | `COMPUTE` | $(+0.42,\; -1.28,\; -0.34)$ | **Yes** | `4.1 ms` | `31.7 Gbps` | `WIN_03 [DIAG]` |

### 5.2 Signal Packets, Raycasting & Subgraph Isolation

* **Bidirectional Signal Packets:** 44 additive point sprites (2 opposing packets per edge) travel along active edges using a custom Gaussian radial falloff fragment shader ($\alpha = e^{-4.8 \|\mathbf{c}\|^2}$), accelerating during `scanning` ($1.55\times$) and `alert` ($1.85\times$) states.
* **Raycast Inspection & Selection:** Invisible spherical hit proxies (`r = 0.135`) enable hover and click detection (`pointerdown` to `pointerup` displacement $< 6\text{ px}$ so camera orbit drags do not trigger accidental clicks). Hovering highlights the node's 1-hop neighborhood and pins `#graph-inspector` to its projected screen position; clicking triggers a scale bounce, sends an HDR pulse wave down all incident edges, locks the rotating diamond `selectionReticle` onto the node, and opens its linked volumetric window.
* **Real-Time Search & Role Filtering (`#topology-bar`):** Filters nodes by ID, role, or linked window (`W1`–`W3`). Unmatched nodes and edges dim to low-luminance SDR context ($0.04$–$0.14$) while matched subgraphs elevate to HDR bloom ($1.15$–$2.60$). If a search query narrows down to a single node, `recomputeMatches()` automatically pins the 3D target lock reticle onto that node.

---

## 6. Choreographed Volumetric Windows & Procedural Imagery

### 6.1 5-Stage GSAP Window Choreography (`SpatialWindowManager`)

Each volumetric window (`#win-01`, `#win-02`, `#win-03`) opens via a 5-stage GSAP timeline:

1. **Laser Deployment Bar (`0.00s`–`0.16s`):** Horizontal glowing `.win-laser-bar` scales outward from `scaleX: 0` to `1`.
2. **Vertical Glass Unfold (`0.10s`–`0.44s`):** Animates `clip-path` from `inset(49% 0% 49% 0%)` to `inset(0% 0% 0% 0%)` using `power3.out`.
3. **Laser Dissipation (`0.22s`–`0.40s`):** Fades the deployment laser as the glass frame stabilizes.
4. **Scanline Image Wipe (`0.18s`–`0.63s`):** Sweeps `.win-scan-wipe` vertically across the viewport canvas (`yPercent: -100` to `120`).
5. **Staggered Telemetry Entrance (`0.22s`+):** Slides `.telem-row` readouts into place with a `0.045s` stagger.

### 6.2 Procedural High-DPI Visualizations (`WindowImageryEngine`)

`WindowImageryEngine` resizes each canvas to match `Math.min(window.devicePixelRatio, 2)` and renders only open windows to conserve GPU/CPU cycles:

* **`WIN_01` (`LIDAR_BATHYMETRY`):** Renders a 15-row $\times$ 26-column perspective-foreshortened wireframe terrain Digital Elevation Model (DEM) with a sweeping horizontal laser scanline and live elevation, point density, and return coherence readouts.
* **`WIN_02` (`OPTICAL_RECON_CAPTURE`):** Projects a 14-vertex 3D Fibonacci sphere lattice with proximity-based edge linking, aperture reticle framing, phase-lock status, and a 32-sample rolling SVG `<polyline>` sparkline.
* **`WIN_03` (`THERMAL_ANOMALY_DIAG`):** Uses an offscreen `280 x 120` scroll-blitted buffer to render a continuous acoustic/thermal waterfall spectrogram with dual Gaussian energy bands, an amber fault-zone bounding box, and live thermal delta metrics.

---

## 7. GSAP State Machine & Kinetic Decoupling

To prevent rotational phase jumps when switching speeds, `createFuiStateController` decouples **continuous frame-delta velocity integration** ($\theta_{t + \Delta t} = \theta_t + \omega \cdot \Delta t$) from **cancellable `gsap.timeline()` transitions**.

### 7.1 State Parameter Matrix (`STATE_PRESETS`)

| Parameter | `idle` | `scanning` | `locked` | `alert` |
| :--- | :--- | :--- | :--- | :--- |
| **HUD Label** | `IDLE_STANDBY` | `ACTIVE_SCANNING` | `TARGET_LOCKED` | `SYSTEM_ALERT` |
| `uScanSpeed` | `0.40` | `2.80` | `0.85` | `4.20` |
| `uAlertMix` | `0.00` | `0.00` | `0.00` | `1.00` |
| `uHdrGain` | `1.30` | `2.10` | `2.65` | `2.80` |
| `bloomPass.strength` | `0.42` | `0.72` | `0.92` | `1.05` (pulsing) |
| `bloomPass.radius` | `0.30` | `0.38` | `0.44` | `0.48` |
| `lockBrackets.scale` | `1.14` | `1.02` | `0.84` | `0.92` |
| `lockBrackets.position.z` | `+0.16` | `+0.25` | `+0.42` | `+0.36` |
| `tickVelocity` ($\text{rad/s}$) | `+0.05` | `+0.32` | `+0.02` | `-0.48` |
| `bracketVelocity` ($\text{rad/s}$) | `-0.07` | `-0.52` | `0.00` (detent) | `+0.75` |
| **Auto-Deployed Windows** | None | `WIN_01` | `WIN_01`, `WIN_02` | `WIN_01`, `WIN_02`, `WIN_03` |

### 7.2 State-Specific Secondary Choreography

* **`locked` Cardinal Detent Snap:** Brakes `bracketVelocity` to `0.0` and snaps `lockBrackets.rotation.z` to the nearest $120^\circ$ ($\frac{2\pi}{3}\text{ rad}$) symmetrical detent using `back.out(2.1)`, accompanied by a $1.48\times$ transient HDR bloom flash.
* **`alert` Elastic Recoil & Heartbeat:** Applies an elastic Z-axis recoil (`z: -0.22` to `0`, `elastic.out(1, 0.52)`) to `reticleRig`, shifts fault-path graph nodes and shaders to warm amber (`#ffaa2b`), and starts an infinite $1.4\text{ Hz}$ (`duration: 0.36s`, `yoyo: true`) bloom pulse.

---

## 8. Procedural Web Audio DSP Engine (`FuiAudioEngine`)

`FuiAudioEngine` synthesizes all UI sound effects in real time using native Web Audio oscillators and exponential gain envelopes, avoiding external audio asset requests:

| Event Method | Oscillator Waveform & Pitch Envelope | Duration | Acoustic Character |
| :--- | :--- | :--- | :--- |
| `playUiClick()` | Sine sweep $1750\text{ Hz} \rightarrow 880\text{ Hz}$ | `32 ms` | Crisp tactile micro-switch tick |
| `playNodeHover(degree)` | Triangle sweep $(920 + 115d)\text{ Hz} \times 1.24$ | `55 ms` | Degree-pitched telemetry ping |
| `playSweepPing(angle)` | 3-sector sine triad (`1180`, `1320`, `1480 Hz`) | `80 ms` | Sector radar sweep ping in `scanning` mode |
| `playWindowOpen(pitch)` | Triangle sweep $220 \rightarrow 980\text{ Hz}$ + `1480 Hz` chime | `340 ms` | Pneumatic glass unfold + harmonic settle |
| `playWindowClose()` | Sine sweep $760\text{ Hz} \rightarrow 210\text{ Hz}$ | `140 ms` | Rapid glass retraction sweep |
| `playStateTransition('locked')` | Sine sub-bass $150 \rightarrow 48\text{ Hz}$ + triangle triad (`880`, `1320`, `1760 Hz`) | `260 ms` | Heavy mechanical lock thud + harmonic chime |
| `playStateTransition('alert')` | Dual staggered sawtooth pulses $620 \rightarrow 460\text{ Hz}$ | `260 ms` | Urgent two-tone warning klaxon |

Audio unlocks automatically on the first `pointerdown` or `keydown` event to comply with browser autoplay policies, and updates the 6-bar `#audio-bars` energy visualizer in the top-left HUD card.

---

## 9. Interactive Controls, Shortcuts & Extension Guide

### 9.1 Pointer & Keyboard Controls

| Input / Shortcut | Action |
| :--- | :--- |
| **Pointer Move** | Tilts the 2.5D/3D reticle rig and CSS volumetric window stage via synchronized parallax |
| **Left-Click Drag** | Orbits camera $360^\circ$ around the reticle volume (`OrbitControls` with damping) |
| **Scroll Wheel / Pinch** | Zooms camera distance between $2.6$ and $12.0$ world units |
| **Hover / Click 3D Node** | Inspects node telemetry, pulses incident edges, and opens its linked volumetric window |
| **Click `NODE_01`–`03` Pill** | Toggles the corresponding volumetric glass window (`WIN_01`, `WIN_02`, or `WIN_03`) |
| `1` / `2` / `3` / `4` | Transitions system state to `idle`, `scanning`, `locked`, or `alert` |
| `W` | Toggles all three volumetric glass windows (`WIN_01`, `WIN_02`, `WIN_03`) simultaneously |
| `G` | Toggles 3D Graph Nodes & Edges visibility |
| `/` | Focuses the Spatial Node-Search input (`QUERY://`) |
| `ArrowUp` / `ArrowDown` / `Enter` | Navigates and selects matching nodes inside the search autocomplete dropdown |
| `Esc` | Clears the active search query and blurs the search input |
| `M` | Mutes or unmutes the procedural Web Audio synthesizer |
| `R` | Smoothly resets the 3D camera and orbit target to the default front HUD viewpoint |

### 9.2 Common Customization Points

* **Adjusting Selective Bloom Sensitivity:** Modify the fourth argument (`threshold`, default `1.05`) in `createFuiComposer()` inside Module 04. Lowering it below `1.0` blooms SDR hairlines; raising it above `1.5` restricts bloom exclusively to peak HDR lock flashes.
* **Adding New Graph Nodes or Edges:** Append entries to `nodeSpecs` and `edgeSpecs` inside `SpatialGraphSystem` (Module 05). Node degrees, neighbor sets, edge pulse buffers, and filter counters are computed automatically at initialization.
* **Integrating Real Telemetry Streams:** Replace the sinusoidal mock formulas inside `WindowImageryEngine.updateTelemetryReadouts()` (Module 02) with WebSocket or `EventSource` telemetry payloads while keeping `AudioContext` and `requestAnimationFrame` decoupled from network arrival rates.