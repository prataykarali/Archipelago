"""
Archipelago Inference Server Entrypoint
Runs the inference engine on port 5151 (ARCHIPELAGO_INFERENCE_PORT).
Uses the xkiro → NVIDIA NIM provider chain for real-time chat & synthesis.

Re-exports the citation-map builder that callers (and the citation-correctness
integration test) reach for on this module.  It lived only in
``archipelago.inference.citations.part01_evidence``, so anything importing the
documented entrypoint got an ``AttributeError`` instead of the map.
"""
from archipelago.apps.inference_app import main
from archipelago.inference.citations import build_concept_citation_map

__all__ = ["build_concept_citation_map", "main"]

if __name__ == "__main__":
    main()