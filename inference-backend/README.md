# inference-backend

AI/ML chat pipeline (port **5051**).

**Current code lives in** `archipelago/inference/` + root `inference_server.py`
during migration. This folder is the target package home.

```bash
# from repo root
export PYTHONPATH=".:ingestion_backend"
python inference_server.py
```

Do **not** import `ingestion_worker` here — use `archipelago.inference.graph_lock`.
