"""
Archipelago Inference Server Entrypoint
Runs the inference engine on port 5151 (ARCHIPELAGO_INFERENCE_PORT).
Uses xkiro / Gemini APIs for real-time chat & pedagogical synthesis.
"""
from archipelago.apps.inference_app import main

if __name__ == "__main__":
    main()
