# Push Archipelago pilot to Hugging Face

## What to publish

| Artifact | Repo type | Contents |
|----------|-----------|----------|
| **Space (demo)** | `space` (Docker) | This app via `Dockerfile.hf` |
| **Model** (optional) | `model` | Fine-tuned `lib-qwen` via `scripts/upload_model_hf.py` |
| **Dataset** (optional) | `dataset` | Rights-cleared pilot PDFs / graph export |

Do **not** upload `.env`, API keys, private e-resource passwords, or copyrighted PDF trees.

## Space setup

1. Create a Docker Space on Hugging Face.
2. Add **Repository secrets**:
   - `OLLAMA_HOST` — remote Ollama GPU endpoint (e.g. `http://gpu-host:11434`), required for SLM synthesis
   - `ARCHIPELAGO_TOKEN` — recommended if Space is public
   - Optional: `ARCHIPELAGO_ERESOURCE_JSON` path content via a private secret file
3. Set Space hardware (GPU recommended for local Ollama synthesis; CPU-only will use grounded fallback only).
4. Push code (from a clean tree, respecting `.hfignore`):

```bash
# Example — replace with your Space id
huggingface-cli login
# Or: git remote add hf https://huggingface.co/spaces/USER/archipelago-pilot
# git push hf main:main
```

5. Root files expected by the Space:
   - `Dockerfile.hf` (rename to `Dockerfile` on the Space root, or set Space Dockerfile path)
   - `requirements.txt`
   - `scripts/ops/hf_space_start.sh` (executable)
   - A small/read-only `okf_graph.db` if you want non-empty retrieval

## Local Docker smoke

```bash
cp Dockerfile.hf Dockerfile
docker build -t archipelago-hf .
docker run --rm -p 7860:7860 \
  -e OLLAMA_HOST="http://host.docker.internal:11434" \
  -e ARCHIPELAGO_TOKEN=dev-token \
  archipelago-hf
curl -s http://127.0.0.1:7860/api/readiness
```

## Model-only upload

```bash
python scripts/upload_model_hf.py \
  --repo-id YOUR_USER/lib-qwen-v5 \
  --token "$HF_TOKEN"
```

## Security checklist before public Space

- [ ] No `.env` in the image
- [ ] `OLLAMA_HOST` set to a reachable GPU Ollama endpoint
- [ ] `ARCHIPELAGO_TOKEN` set for mutating/chat endpoints
- [ ] E-resource credentials not baked into the image
- [ ] Rotate any key that was ever pasted into chat/logs
