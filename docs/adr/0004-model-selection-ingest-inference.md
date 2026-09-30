# ADR 0004: Decoupled Model Selection: lib-qwen for Ingestion and qwen3.5:0.8b for Inference

## Status
Accepted

## Context
The supplied specification proposed a fine-tuned model referenced as `Qwen/Qwen2.5-0.8B-Instruct`. Official model registry auditing revealed that this identifier does not exist. Furthermore, conflating extraction workloads (offline, high schema precision, structured output) with interactive chat synthesis (real-time streaming, conversational tone, pedagogical feedback) degrades system performance.

## Decision
1. **Model Ingestion Extractor:** Deploy fine-tuned **`lib-qwen`** (`lib-qwen:latest` / `lib-qwen:local` in Ollama / local GGUF). It runs offline or during batch ingestion jobs to convert chunked text into structured OKF concepts. It is never loaded during real-time user chat.
2. **Inference Synthesizer:** Deploy **`qwen3.5:0.8b`** via local Ollama with `think=False` streaming. It handles user dialogue, diagnostic MCQ generation, and pedagogical roadmap explanations.
3. **Cloud & Extractive Fallback:** High-traffic cloud failover (Gemini Flash) is permitted only for non-restricted public context under the Data Egress Policy. If all neural models fail, the system falls back to a deterministic extractive template.

## Consequences
- Clean separation of concerns between batch extraction and real-time generation.
- Zero VRAM contention between ingestion tasks and user-facing inference servers.
- Adheres strictly to verified local and official model registries.
