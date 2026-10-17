"""Cloud Synchronization Pipeline for Hugging Face Hub and Vercel.

Automates the synchronization of:
1. Ingested scholarly training datasets and OKF evidence manifests to Hugging Face (Prataykarali/graphier).
2. Fine-tuned SLM model checkpoints / LoRA adapters to Hugging Face.
3. Live catalog manifests and edge cache updates to Vercel (https://archipelago-blond.vercel.app).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import time
from typing import Any
import urllib.error
import urllib.request

from dotenv import load_dotenv

logger = logging.getLogger("archipelago.scholarly.cloud_sync")

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")

DEFAULT_HF_REPO = os.getenv("ARCHIPELAGO_SCHOLARLY_HF_REPO", "Prataykarali/graphier")
DEFAULT_VERCEL_URL = "https://archipelago-blond.vercel.app"


class CloudSyncPipeline:
    """Manages cloud synchronization to Hugging Face Hub and Vercel."""

    def __init__(
        self,
        hf_token: str | None = None,
        hf_repo_id: str | None = None,
        vercel_url: str | None = None,
        deploy_hook: str | None = None,
    ):
        self.hf_token = hf_token or os.getenv("HF_TOKEN")
        self.hf_repo_id = hf_repo_id or DEFAULT_HF_REPO
        self.vercel_url = (
            vercel_url or os.getenv("VERCEL_PROJECT_URL") or DEFAULT_VERCEL_URL
        ).rstrip("/")
        self.deploy_hook = deploy_hook or os.getenv("VERCEL_DEPLOY_HOOK_URL")

    # -------------------------------------------------------------------------
    # Hugging Face Synchronization
    # -------------------------------------------------------------------------
    def sync_to_huggingface(
        self,
        upload_datasets: bool = True,
        upload_manifests: bool = True,
        upload_lora_adapters: bool = True,
    ) -> dict[str, Any]:
        """Synchronize ingested datasets, manifests, and fine-tuned models to Hugging Face."""
        if not self.hf_token:
            logger.warning("HF_TOKEN not configured. Skipping Hugging Face upload.")
            return {"status": "skipped", "reason": "HF_TOKEN not found"}

        try:
            from huggingface_hub import HfApi
        except ImportError:
            logger.error("huggingface_hub package is not installed.")
            return {"status": "failed", "reason": "huggingface_hub not installed"}

        api = HfApi(token=self.hf_token)
        uploaded_files: list[str] = []
        errors: list[str] = []

        logger.info("Starting sync to Hugging Face repository: %s", self.hf_repo_id)

        # 1. Sync SLM Training Datasets
        if upload_datasets:
            dataset_files = [
                (
                    "data/datasets/dataset1_pedagogical_revamped.jsonl",
                    "datasets/dataset1_pedagogical_revamped.jsonl",
                ),
                (
                    "data/datasets/dataset2_scholarly_evidence.jsonl",
                    "datasets/dataset2_scholarly_evidence.jsonl",
                ),
                ("data/datasets/slm_ingestion_queue.jsonl", "datasets/slm_ingestion_queue.jsonl"),
            ]
            for local_rel, repo_path in dataset_files:
                local_path = ROOT / local_rel
                if local_path.is_file() and local_path.stat().st_size > 0:
                    try:
                        logger.info(
                            "Uploading %s -> %s (%d bytes)",
                            local_rel,
                            repo_path,
                            local_path.stat().st_size,
                        )
                        api.upload_file(
                            path_or_fileobj=str(local_path),
                            path_in_repo=repo_path,
                            repo_id=self.hf_repo_id,
                            repo_type="dataset",
                            commit_message=f"data: update {Path(repo_path).name} from automated harvest",
                        )
                        uploaded_files.append(repo_path)
                    except Exception as e:
                        logger.error("Error uploading %s to HF: %s", local_rel, e)
                        errors.append(f"{repo_path}: {e!s}")

        # 2. Sync Live Scholarly Manifests
        if upload_manifests:
            manifest_files = [
                (
                    "data/catalogs/live_scholarly_manifest.json",
                    "catalogs/live_scholarly_manifest.json",
                ),
                (
                    "data/catalogs/latest_harvest_summary.json",
                    "catalogs/latest_harvest_summary.json",
                ),
            ]
            for local_rel, repo_path in manifest_files:
                local_path = ROOT / local_rel
                if local_path.is_file() and local_path.stat().st_size > 0:
                    try:
                        logger.info("Uploading %s -> %s", local_rel, repo_path)
                        api.upload_file(
                            path_or_fileobj=str(local_path),
                            path_in_repo=repo_path,
                            repo_id=self.hf_repo_id,
                            repo_type="dataset",
                            commit_message="feat(manifest): sync live scholarly manifest",
                        )
                        uploaded_files.append(repo_path)
                    except Exception as e:
                        logger.error("Error uploading %s to HF: %s", local_rel, e)
                        errors.append(f"{repo_path}: {e!s}")

        # 3. Sync LoRA Model Adapters (if trained and present)
        if upload_lora_adapters:
            lora_dir = ROOT / "models/lib_qwen_scholarly_lora"
            if lora_dir.is_dir():
                for f_name in [
                    "adapter_config.json",
                    "adapter_model.safetensors",
                    "training_args.bin",
                    "special_tokens_map.json",
                ]:
                    local_f = lora_dir / f_name
                    if local_f.is_file():
                        repo_path = f"models/lib_qwen_scholarly_lora/{f_name}"
                        try:
                            logger.info("Uploading LoRA adapter %s", f_name)
                            api.upload_file(
                                path_or_fileobj=str(local_f),
                                path_in_repo=repo_path,
                                repo_id=self.hf_repo_id,
                                repo_type="dataset",
                                commit_message="model: sync fine-tuned LoRA weights",
                            )
                            uploaded_files.append(repo_path)
                        except Exception as e:
                            logger.warning("Could not upload LoRA adapter %s: %s", f_name, e)

        return {
            "status": "success" if not errors else ("partial" if uploaded_files else "failed"),
            "uploaded_files": uploaded_files,
            "errors": errors,
            "repo_id": self.hf_repo_id,
        }

    # -------------------------------------------------------------------------
    # Vercel Synchronization
    # -------------------------------------------------------------------------
    def sync_to_vercel(self) -> dict[str, Any]:
        """Synchronize fresh manifests to local web data paths and trigger Vercel deployment/revalidation."""
        results: dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "vercel_url": self.vercel_url,
            "manifest_prepared": False,
            "deploy_hook_triggered": False,
        }

        # 1. Prepare a distinct scholarly snapshot for the hosted app build.
        # A local write alone does not publish an existing Vercel deployment.
        live_manifest_path = ROOT / "data/catalogs/live_scholarly_manifest.json"
        showcase_data_path = ROOT / "host_inference/fixtures/live_scholarly_manifest.json"

        if live_manifest_path.is_file():
            try:
                with open(live_manifest_path, encoding="utf-8") as f:
                    manifest_data = json.load(f)

                # Write formatted showcase catalog
                with open(showcase_data_path, "w", encoding="utf-8") as f:
                    json.dump(manifest_data, f, indent=2)

                results["manifest_prepared"] = True
                logger.info("Prepared hosted scholarly snapshot at %s", showcase_data_path)
            except Exception as e:
                logger.error("Failed updating showcase data for Vercel: %s", e)
                results["error"] = str(e)

        # 2. Trigger the configured deployment hook. This only requests a build;
        # it does not prove that the new local snapshot was deployed.
        if self.deploy_hook:
            logger.info("Triggering Vercel Deploy Hook: %s", self.deploy_hook)
            try:
                req = urllib.request.Request(self.deploy_hook, method="POST", data=b"{}")
                with urllib.request.urlopen(req, timeout=15) as resp:
                    results["deploy_hook_triggered"] = resp.status in [200, 201]
                    logger.info("Vercel Deploy Hook returned status %d", resp.status)
            except Exception as e:
                logger.warning("Vercel Deploy Hook trigger failed: %s", e)
                results["deploy_hook_error"] = str(e)
        else:
            # Revalidation ping to live site
            try:
                ping_url = f"{self.vercel_url}/api/health"
                req = urllib.request.Request(
                    ping_url, headers={"User-Agent": "Archipelago-Cloud-Sync/1.0"}
                )
                with urllib.request.urlopen(req, timeout=8) as resp:
                    results["live_site_reachable"] = resp.status == 200
            except Exception:
                # Root site ping fallback
                try:
                    req = urllib.request.Request(
                        self.vercel_url, headers={"User-Agent": "Archipelago-Cloud-Sync/1.0"}
                    )
                    with urllib.request.urlopen(req, timeout=8) as resp:
                        results["live_site_reachable"] = resp.status == 200
                except Exception as e:
                    results["live_site_reachable"] = False
                    logger.info("Vercel site ping returned: %s", e)

        return results

    # -------------------------------------------------------------------------
    # Unified Cloud Sync
    # -------------------------------------------------------------------------
    def run_all_sync(self) -> dict[str, Any]:
        """Execute both Hugging Face and Vercel sync jobs."""
        logger.info("=== Running Unified Cloud Sync (Hugging Face + Vercel) ===")
        hf_result = self.sync_to_huggingface()
        vercel_result = self.sync_to_vercel()

        summary = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "huggingface": hf_result,
            "vercel": vercel_result,
        }

        sync_log_path = ROOT / "data/catalogs/latest_cloud_sync.json"
        with open(sync_log_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        logger.info("Cloud sync complete. Logged to %s", sync_log_path)
        return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    sync = CloudSyncPipeline()
    out = sync.run_all_sync()
    print(json.dumps(out, indent=2))
