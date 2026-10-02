// Auto-split from ui/chat/index.html — centralised mutable UI state.
// All modules read/write these through this single object.
export const state = {
  width: window.innerWidth,
  height: window.innerHeight,
  isDragging: false,
  dragStart: { x: 0, y: 0 },
  activeNode: null,
  hoverNode: null,
  nodesG: [],
  edgesG: [],
  nmG: {},
  texturesLoaded: 0,
  linkParticles: [],
};
