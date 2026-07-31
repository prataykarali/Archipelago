# ==============================================================================
# 🚀 1-CLICK GOOGLE COLAB FREE T4 GPU INGESTION SCRIPT
# Runs fine-tuned Prataykarali/lib-qwen on Colab T4 GPU (~350 tokens/sec)
# ==============================================================================

"""
INSTRUCTIONS FOR GOOGLE COLAB:
1. Open https://colab.research.google.com/
2. Click "New Notebook"
3. Go to Runtime -> Change runtime type -> Select "T4 GPU"
4. Paste and run Cell 1 (Setup & Install):

!pip install -q huggingface_hub kuzu pymupdf ollama

5. Paste and run Cell 2 (Run Ingestion at 350+ tokens/sec):

import os
# Set your Hugging Face token via Colab secrets or environment variable:
#   from google.colab import userdata
#   os.environ["HF_TOKEN"] = userdata.get('HF_TOKEN')
# or: os.environ["HF_TOKEN"] = "your_hf_token_here"

!git clone https://github.com/Prataykarali/libraryAI.git || true
%cd libraryAI

!curl -fsSL https://ollama.com/install.sh | sh
!ollama serve > /dev/null 2>&1 &

import time
time.sleep(5)

# Pull fine-tuned model or run qwen3.5:0.8b
!ollama run qwen3.5:0.8b "Hello"

!python scripts/ops/ingest_real_lib.py

# Auto-sync results to HuggingFace
from huggingface_hub import HfApi
api = HfApi(token=os.environ["HF_TOKEN"])
api.upload_file(
    path_or_fileobj="okf_graph.db",
    path_in_repo="okf_graph.db",
    repo_id="Prataykarali/archipelago-books-cs",
    repo_type="dataset"
)
api.upload_file(
    path_or_fileobj="okf_results.json",
    path_in_repo="okf_results.json",
    repo_id="Prataykarali/archipelago-books-cs",
    repo_type="dataset"
)
print("✅ Ingestion & HuggingFace Graph Sync Complete!")
"""
