"""Library catalog package — split from the former library_catalog_api.py monolith."""

from archipelago.inference.library_catalog.part01_ods import (
    CATALOG_COLORS,
    parse_ods_rows,
)
from archipelago.inference.library_catalog.part01_ods import (
    display_title as _display_title,
)
from archipelago.inference.library_catalog.part02_koha import (
    load_holdings,
    load_journals,
    load_subject_counts,
    load_subject_titles,
)
from archipelago.inference.library_catalog.part03_prominent import PROMINENT_EBOOKS
from archipelago.inference.library_catalog.part04_shelf import (
    build_pearson_reader_url,
    build_prominent_ebook_entries,
)
from archipelago.inference.library_catalog.part05_payload import (
    build_library_data_payload,
    load_graph_stats,
    load_local_papers,
    load_pearson_books,
)

__all__ = [
    "CATALOG_COLORS",
    "PROMINENT_EBOOKS",
    "_display_title",
    "build_library_data_payload",
    "build_pearson_reader_url",
    "build_prominent_ebook_entries",
    "load_graph_stats",
    "load_holdings",
    "load_journals",
    "load_local_papers",
    "load_pearson_books",
    "load_subject_counts",
    "load_subject_titles",
    "parse_ods_rows",
]
