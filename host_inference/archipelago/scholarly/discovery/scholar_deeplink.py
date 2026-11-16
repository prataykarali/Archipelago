"""Google Scholar Outbound Deep-Link Generator.

Per Master Coder Handoff Rule 1:
'Do not scrape Google Scholar as the ingestion backbone. Scholar may be an outbound human-verification link only.'
"""

import urllib.parse


def generate_scholar_url(title: str, author: str | None = None) -> str:
    """Generate an authoritative Google Scholar verification URL for a paper or topic."""
    query = f'"{title}"'
    if author:
        query += f" {author}"
    return f"https://scholar.google.com/scholar?q={urllib.parse.quote(query)}"


def generate_scholar_author_url(author_name: str) -> str:
    """Generate an authoritative Google Scholar author-search verification URL."""
    cleaned = " ".join((author_name or "").split())
    return f'https://scholar.google.com/scholar?q={urllib.parse.quote(f"author:{chr(34)}{cleaned}{chr(34)}")}'


def generate_scholar_cluster_url(cluster_id: str) -> str:
    """Generate Scholar cluster link if a cluster ID is known."""
    return f"https://scholar.google.com/scholar?cluster={urllib.parse.quote(cluster_id)}"
