/** Stable UI ViewModel — components never depend on raw wire format. */
export type ChatViewModel = {
  status: "idle" | "streaming" | "error" | "degraded";
  route: string | null;
  anchor: { id: string; name: string } | null;
  prerequisites: { id: string; name: string }[];
  unlocks: { id: string; name: string }[];
  citations: { evidence_id: string; title: string; page_number?: number }[];
  answerMarkdown: string;
  errorMessage?: string;
};
