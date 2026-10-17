// Auto-split from ui/chat/index.html — centralised mutable UI state.
// All modules read/write these through this single object.
export const state = {
  allNodes: [],
  allEdges: [],
  nodeMap: {},
  currentView: 'books',
  currentBook: null,
  simulation: null,
  svgZoom: null,
  nSel: null,
  eSel: null,
  flashcardOpen: false,
};
