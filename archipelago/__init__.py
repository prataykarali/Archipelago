"""Archipelago — feature packages (inference, ingestion, okf, core, graph)."""
import pkgutil
from pathlib import Path

__path__ = pkgutil.extend_path(__path__, __name__)

_src_archipelago = Path(__file__).resolve().parent.parent / "src" / "archipelago"
if _src_archipelago.is_dir() and str(_src_archipelago) not in __path__:
    __path__.append(str(_src_archipelago))
