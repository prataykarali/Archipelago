// Re-publish the public surface on window so inline onclick handlers and
// legacy classic scripts keep working, exactly like the old global script.
import { CLRS, TCLRS, canvas, checkTextures, ctx, draw, initGraph, isNeighbor, loop, spawnParticles, textures, totalTextures, transform, update } from './00-canvas.js';
import { closePanel, findNodeAt, getMousePos, mkList, openPanel, panel } from './01-get-mouse-pos.js';

const api = {
  CLRS,
  TCLRS,
  canvas,
  checkTextures,
  closePanel,
  ctx,
  draw,
  findNodeAt,
  getMousePos,
  initGraph,
  isNeighbor,
  loop,
  mkList,
  openPanel,
  panel,
  spawnParticles,
  textures,
  totalTextures,
  transform,
  update,
};
for (const [name, value] of Object.entries(api)) {
  window[name] = value;
}
