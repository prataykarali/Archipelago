"""Combined D14.1 new open-access source registry across all 12 domains."""

from __future__ import annotations

from archipelago.corpus.catalog_types import SourceSpec
from archipelago.corpus.oa_sources_systems import build_systems_oa_sources
from archipelago.corpus.oa_sources_theory_se import build_theory_se_oa_sources


def build_d14_new_oa_sources() -> list[SourceSpec]:
    """Return all new license-verified OA sources across all 12 canonical domains."""
    return build_systems_oa_sources() + build_theory_se_oa_sources()
