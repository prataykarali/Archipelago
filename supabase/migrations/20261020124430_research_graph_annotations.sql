-- Staff-curated details for existing institutional graph concepts.
-- Browser roles have no direct Data API access; the hosted API verifies roles.
CREATE TABLE public.research_graph_annotations (
    concept_id text PRIMARY KEY,
    summary text NOT NULL,
    source_url text,
    updated_by uuid NOT NULL REFERENCES auth.users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT research_graph_summary_length CHECK (char_length(summary) BETWEEN 1 AND 2000),
    CONSTRAINT research_graph_url_length CHECK (source_url IS NULL OR char_length(source_url) <= 500)
);

ALTER TABLE public.research_graph_annotations ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.research_graph_annotations FROM anon, authenticated, PUBLIC;
GRANT SELECT, INSERT, UPDATE ON public.research_graph_annotations TO service_role;
