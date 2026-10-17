// Re-publish the public surface on window so inline onclick handlers and
// legacy classic scripts keep working, exactly like the old global script.
import { BOOKS, EC, EI, EO, EW, TC, bk, checkGraphStaffAccess, destroyGraph, escapeHtml, highlightParam, nC, nR, processData, rid, setTab, urlParams } from './00-escape-html.js';
import { BooksModule, showBooks, showConcepts, showCrossBook } from './01-books-module.js';
import { buildConceptGraph } from './02-build-concept-graph.js';
import { closeFlashcard, openFC, srchI, srchR } from './03-open-fc.js';

const api = {
  BOOKS,
  BooksModule,
  EC,
  EI,
  EO,
  EW,
  TC,
  bk,
  buildConceptGraph,
  checkGraphStaffAccess,
  closeFlashcard,
  destroyGraph,
  escapeHtml,
  highlightParam,
  nC,
  nR,
  openFC,
  processData,
  rid,
  setTab,
  showBooks,
  showConcepts,
  showCrossBook,
  srchI,
  srchR,
  urlParams,
};
for (const [name, value] of Object.entries(api)) {
  window[name] = value;
}
