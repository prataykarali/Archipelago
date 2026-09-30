"""Re-export KuzuGraphEngine in archipelago.graph.engine for direct imports."""
import importlib.util
from pathlib import Path

_src_engine_path = Path(__file__).resolve().parents[2] / "src" / "archipelago" / "graph" / "engine.py"
_spec = importlib.util.spec_from_file_location("_src_engine", _src_engine_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

KuzuGraphEngine = _mod.KuzuGraphEngine
_swap_lock = _mod._swap_lock
_active_instances = _mod._active_instances

__all__ = ["KuzuGraphEngine", "_swap_lock", "_active_instances"]
