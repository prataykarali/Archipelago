"""Backwards-compatibility shim — library catalog moved to library_catalog/ package."""

from archipelago.inference.library_catalog import (  # noqa: F401
    CATALOG_COLORS,
    PROMINENT_EBOOKS,
    _display_title,
    build_library_data_payload,
    build_pearson_reader_url,
    build_prominent_ebook_entries,
    load_graph_stats,
    load_holdings,
    load_journals,
    load_local_papers,
    load_pearson_books,
    load_subject_counts,
    load_subject_titles,
    parse_ods_rows,
)
