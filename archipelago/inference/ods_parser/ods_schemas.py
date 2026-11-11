"""Header schemas for institutional ODS exports."""

from __future__ import annotations

from typing import Any

ODS_SCHEMA_SUBJECT = {
    "name": "subject_report",
    "expected_headers": [
        "subject / department",
        "title count",
        "volume/issue count",
    ],
    "optional_headers": (),
    "header_aliases": {
        "subject / department": (
            "subject",
            "department",
            "subject/department",
            "subject department",
            "subject / department",
        ),
        "title count": (
            "titles",
            "title count",
            "count of titles",
            "titles count",
            "total titles",
            "total title",
        ),
        "volume/issue count": (
            "volume/issue",
            "vol/issue",
            "volume count",
            "issue count",
            "volume/issue count",
        ),
    },
}


ODS_SCHEMA_SUBJECT_COUNTS = {
    "name": "subject_report",
    "expected_headers": ["subject", "total titles"],
    "optional_headers": (),
    "header_aliases": {
        "subject": ("subject", "department", "subject / department"),
        "total titles": ("total titles", "title count", "titles", "count of titles"),
    },
    "canonical_map": {
        "subject": "subject / department",
        "total titles": "title count",
    },
}


ODS_SCHEMA_JOURNAL = {
    "name": "journal_report",
    "expected_headers": [
        "journal title",
        "issn",
        "issue count",
        "publisher",
    ],
    "optional_headers": (),
    "header_aliases": {
        "journal title": ("journal", "title", "journal name", "publication title", "journal title"),
        "issn": ("issn", "issn number", "issn no"),
        "issue count": ("issues", "issue count", "number of issues", "count"),
        "publisher": ("publisher", "publisher name", "published by"),
    },
}


ODS_SCHEMA_JOURNAL_ISSUES = {
    "name": "journal_report",
    "expected_headers": [
        "journal title",
        "issue number/volume",
        "published date",
        "issue status",
    ],
    "optional_headers": ("published date", "issue status"),
    "header_aliases": {
        "journal title": ("journal title", "journal", "title"),
        "issue number/volume": (
            "issue number/volume",
            "issue number",
            "volume",
            "vol/issue",
            "issue number/volume",
        ),
        "published date": ("published date", "date", "pub date"),
        "issue status": ("issue status", "status"),
    },
    "canonical_map": {
        "journal title": "journal title",
        "issue number/volume": "issue count",
        "published date": "published date",
        "issue status": "issue status",
    },
}


ODS_SCHEMA_KEYWORD = {
    "name": "keyword_report",
    "expected_headers": [
        "title",
        "author",
        "subject keyword",
        "call number",
    ],
    "optional_headers": (),
    "header_aliases": {
        "title": ("title", "book title", "publication title", "item title"),
        "author": ("author", "authors", "author(s)", "creator"),
        "subject keyword": (
            "subject keyword",
            "subject",
            "keyword",
            "keywords",
            "subject heading",
            "tags",
        ),
        "call number": (
            "call number",
            "call no",
            "call #",
            "classification no",
            "shelf mark",
            "accn nos.",
            "accn nos",
            "accession",
        ),
    },
}


ODS_SCHEMA_KEYWORD_TITLES = {
    "name": "keyword_report",
    "expected_headers": ["title", "author"],
    "optional_headers": (
        "author",
        "publisher",
        "biblionumber",
        "accn nos.",
        "no. of copies",
    ),
    "header_aliases": {
        "title": ("title", "book title", "publication title"),
        "author": ("author", "authors", "author(s)"),
        "publisher": ("publisher",),
        "biblionumber": ("biblionumber", "biblio number"),
        "accn nos.": ("accn nos.", "accn nos", "accession"),
        "no. of copies": ("no. of copies", "copies"),
    },
    "canonical_map": {
        "title": "title",
        "author": "author",
        "publisher": "publisher",
        "accn nos.": "call number",
        "biblionumber": "biblionumber",
    },
}


ODS_SCHEMA_VARIANTS: list[dict[str, Any]] = [
    ODS_SCHEMA_SUBJECT,
    ODS_SCHEMA_SUBJECT_COUNTS,
    ODS_SCHEMA_JOURNAL,
    ODS_SCHEMA_JOURNAL_ISSUES,
    ODS_SCHEMA_KEYWORD,
    ODS_SCHEMA_KEYWORD_TITLES,
]


ODS_SCHEMA_REGISTRY: dict[str, dict[str, Any]] = {
    "subject_report": ODS_SCHEMA_SUBJECT,
    "journal_report": ODS_SCHEMA_JOURNAL,
    "keyword_report": ODS_SCHEMA_KEYWORD,
}


FIELD_FALLBACKS: dict[str, str] = {
    "author": "Unknown / Institutional",
    "subject keyword": "uncategorized",
    "subject keyword ": "uncategorized",
    "publisher": "Unknown Publisher",
    "call number": "Unassigned",
    "issn": "0000-0000",
    "volume/issue count": "0",
    "title count": "0",
    "issue count": "0",
}
