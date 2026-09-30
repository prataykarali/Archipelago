"""DOI (Digital Object Identifier) Link Resolver."""
from __future__ import annotations

import logging
import re
from typing import Any
import requests

logger = logging.getLogger("archipelago.resolver.doi")

DOI_PATTERN = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+")


def extract_doi(input_str: str) -> str | None:
    """Extract a DOI string from a URL or raw DOI string."""
    match = DOI_PATTERN.search(input_str)
    if match:
        return match.group(0).rstrip(".")
    return None


def resolve_doi(input_str: str, timeout: int = 8) -> dict[str, Any]:
    """Resolve a DOI or DOI URL to its canonical target page."""
    doi = extract_doi(input_str)
    if not doi:
        return {
            "working": False,
            "url": input_str,
            "doi_url": f"https://doi.org/{input_str}" if input_str else None,
            "error": "Invalid DOI format",
            "source": "doi",
        }


    doi_url = f"https://doi.org/{doi}"
    
    # Try resolving doi.org via handle API first for speed
    api_url = f"https://doi.org/api/handles/{doi}"
    try:
        resp = requests.get(api_url, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            values = data.get("values", [])
            for val in values:
                if val.get("type") == "URL":
                    target = val.get("data", {}).get("value")
                    if target:
                        return {
                            "working": True,
                            "doi": doi,
                            "url": target,
                            "canonical_url": target,
                            "doi_url": doi_url,
                            "source": "doi",
                        }
    except Exception as exc:
        logger.debug("DOI handle API resolution failed: %s", exc)

    # Fallback: HTTP redirect follow
    try:
        head_resp = requests.head(doi_url, allow_redirects=True, timeout=timeout)
        if head_resp.status_code < 400:
            return {
                "working": True,
                "doi": doi,
                "url": str(head_resp.url),
                "canonical_url": str(head_resp.url),
                "doi_url": doi_url,
                "source": "doi",
            }
    except Exception as exc:
        logger.debug("DOI HTTP redirect follow failed: %s", exc)

    return {
        "working": True,
        "doi": doi,
        "url": doi_url,
        "canonical_url": doi_url,
        "doi_url": doi_url,
        "source": "doi",
    }

