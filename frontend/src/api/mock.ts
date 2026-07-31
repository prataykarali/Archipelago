import type { ChatViewModel } from "./types";

/** Offline / degraded fallback — keeps layout painted without backend. */
export function mockChatViewModel(query: string): ChatViewModel {
  return {
    status: "degraded",
    route: "mock",
    anchor: null,
    prerequisites: [],
    unlocks: [],
    citations: [],
    answerMarkdown:
      "Backend unreachable. UI is still interactive (mock fallback). " +
      "Retry when inference :5051 is up. Query was: " +
      query.slice(0, 120),
    errorMessage: "inference_unreachable",
  };
}
