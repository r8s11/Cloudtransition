// Test-only browser init script. It observes real GPU calls; it supplies no renderer or fake context.
(() => {
  const proof = window.__depthGPU = { contexts: 0, draws: 0, deletedBuffers: 0, deletedPrograms: 0, instances: [], frames: [] };
  const contextStates = new WeakMap();
  const locationNames = new WeakMap();
  const originalGetContext = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (kind, ...args) {
    const context = originalGetContext.call(this, kind, ...args);
    if (context && (kind === 'webgl2' || kind === 'webgl') && !contextStates.has(context)) {
      proof.contexts++;
      contextStates.set(context, { canvas: this, projection: null, modelView: null });
    }
    return context;
  };
  const recordDraw = (context, count) => {
    proof.draws++;
    const state = contextStates.get(context);
    if (count != null) {
      proof.instances.push(count);
      if (proof.instances.length > 1000) proof.instances.splice(0, 500);
    }
    if (state && count > 20 && state.projection && state.modelView) {
      proof.lastFileDraw = { count, projection: state.projection.slice(), modelView: state.modelView.slice(), canvas: { width: state.canvas.clientWidth, height: state.canvas.clientHeight } };
    }
  };
  for (const Constructor of [window.WebGLRenderingContext, window.WebGL2RenderingContext]) {
    if (!Constructor) continue;
    const prototype = Constructor.prototype;
    const wrap = (name, observe) => {
      if (!Object.prototype.hasOwnProperty.call(prototype, name)) return;
      const original = prototype[name];
      prototype[name] = function (...args) {
        const result = original.apply(this, args);
        observe(this, args, result);
        return result;
      };
    };
    wrap('getUniformLocation', (_context, args, location) => { if (location) locationNames.set(location, args[1]); });
    wrap('uniformMatrix4fv', (context, args) => {
      const state = contextStates.get(context);
      if (!state) return;
      const name = locationNames.get(args[0]);
      if (name === 'projectionMatrix') state.projection = Array.from(args[2]);
      if (name === 'modelViewMatrix') state.modelView = Array.from(args[2]);
    });
    wrap('drawElements', context => recordDraw(context));
    wrap('drawArrays', context => recordDraw(context));
    wrap('drawElementsInstanced', (context, args) => recordDraw(context, args[4]));
    wrap('drawArraysInstanced', (context, args) => recordDraw(context, args[3]));
    wrap('deleteBuffer', () => proof.deletedBuffers++);
    wrap('deleteProgram', () => proof.deletedPrograms++);
  }
  // Project real layout points with the matrices submitted to the actual file draw.
  // Input: [{path, position: [x,y,z]}]. It does not move or select anything.
  window.__depthProject = points => {
    const frame = proof.lastFileDraw;
    const canvas = document.querySelector('.graph canvas');
    if (!frame || !canvas || frame.count !== points.length) throw new Error('No matching instanced file draw');
    const rectangle = canvas.getBoundingClientRect();
    const multiply = (matrix, vector) => [0, 1, 2, 3].map(row =>
      matrix[row] * vector[0] + matrix[row + 4] * vector[1] +
      matrix[row + 8] * vector[2] + matrix[row + 12] * vector[3]);
    return points.map(point => {
      const view = multiply(frame.modelView, [...point.position, 1]);
      const clip = multiply(frame.projection, view);
      return { path: point.path, x: rectangle.left + (clip[0] / clip[3] + 1) * rectangle.width / 2,
        y: rectangle.top + (1 - clip[1] / clip[3]) * rectangle.height / 2, z: clip[2] / clip[3] };
    }).filter(point => point.z > -1 && point.z < 1 &&
      point.x > rectangle.left + 16 && point.x < rectangle.right - 16 &&
      point.y > rectangle.top + 16 && point.y < rectangle.bottom - 16);
  };
})();
