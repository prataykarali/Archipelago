"""Backwards-compatibility shim — library catalog moved to library_catalog/ package."""
from archipelago.inference.library_catalog import (  # noqa: F401
    CATALOG_COLORS,
    _display_title,
    parse_ods_rows,
    load_holdings,
    load_journals,
    load_subject_counts,
    load_subject_titles,
    PROMINENT_EBOOKS,
    build_pearson_reader_url,
    build_prominent_ebook_entries,
    build_library_data_payload,
    load_graph_stats,
    load_local_papers,
    load_pearson_books,
)
