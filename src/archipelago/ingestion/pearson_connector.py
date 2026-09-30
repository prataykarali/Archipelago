"""
Pearson eLibrary Authenticated Connector & Deep-Link Catalog Engine.

Extracts and manages textbook manifests, ISBN identifiers, subscription tokens,
and exact reader deep-linking URLs without triggering DRM stream blocking.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import logging
import os
from pathlib import Path
import re
from typing import Optional

logger = logging.getLogger("archipelago.ingestion.pearson_connector")

PEARSON_BASE_WR = "https://ebooks.elibrary.in.pearson.com/wr"

# Academic domain categorization heuristics for Pearson titles
DOMAIN_KEYWORDS = {
    "Artificial Intelligence & Machine Learning": [
        "artificial intelligence", "machine learning", "neural network", "speech and language",
        "computer vision", "deep learning"
    ],
    "Computer Networks & Security": [
        "computer networks", "cryptography", "network security", "wireless communications",
        "data and computer communications"
    ],
    "Operating Systems & Architecture": [
        "operating systems", "computer system architecture", "computer organization", "iot fundamentals"
    ],
    "Compilers & Algorithms": [
        "compilers", "analysis of algorithms", "data structures", "problem solving and programming"
    ],
    "Databases & Web Engineering": [
        "database system", "web development", "web technology"
    ],
    "Electronics & Embedded Systems": [
        "microcontroller", "embedded systems", "electronic devices", "digital logic",
        "digital design", "basic electrical", "op-amps", "solid state"
    ],
    "Signal Processing & Mathematics": [
        "digital signal processing", "digital image processing", "probability", "quantitative"
    ],
}


def classify_academic_domain(title: str) -> str:
    """Map textbook title to standard academic domain."""
    tl = title.lower()
    for domain, kws in DOMAIN_KEYWORDS.items():
        if any(kw in tl for kw in kws):
            return domain
    return "General Computer Science & Engineering"


@dataclass
class PearsonBook:
    """Normalized metadata and reader deep-linking contract for a Pearson textbook."""

    id: str
    title: str
    author: str
    isbn: str
    book_type: str  # "pdf" | "reflowable"
    page_count: int
    subscription_id: str
    domain: str
    cover_url: str = ""
    ingestion_tier: str = "deep"  # Pearson books receive deep extraction
    sections: list[dict] = field(default_factory=list)

    @property
    def reader_base_url(self) -> str:
        """Base web reader URL with institutional subscription token."""
        sub_param = f"?subscriptionId={self.subscription_id}" if self.subscription_id else ""
        if self.book_type.lower() == "pdf":
            return f"{PEARSON_BASE_WR}/pdfviewer.html{sub_param}#book/{self.id}"
        return f"{PEARSON_BASE_WR}/index.html{sub_param}#book/{self.id}"

    def get_page_reader_url(self, page_number: int | None = None) -> str:
        """Construct exact reader deep-link for a cited page number."""
        base = self.reader_base_url
        if page_number is not None and self.book_type.lower() == "pdf":
            return f"{base}/page/{page_number}"
        return base

    def to_dict(self) -> dict:
        d = asdict(self)
        d["reader_base_url"] = self.reader_base_url
        return d


@dataclass
class PearsonCatalog:
    """Catalog of all available institutional Pearson textbooks."""

    books: list[PearsonBook] = field(default_factory=list)

    @classmethod
    def from_readium_data(cls, readium_raw_data: list[dict]) -> PearsonCatalog:
        """Parse raw ReadiumLibraryData from Pearson eLibrary session."""
        books = []
        for raw in readium_raw_data:
            b_id = raw.get("id") or ""
            title = (raw.get("title") or "").strip()
            author = (raw.get("author") or "").strip()
            isbn = (raw.get("isbn") or "").strip()
            b_type = (raw.get("bookType") or "pdf").lower()
            page_count = int(raw.get("bookPageCount") or 0)
            cover = raw.get("cover") or ""

            # Extract active subscription ID
            sub_id = ""
            subscriptions = raw.get("subscriptions") or []
            if subscriptions and isinstance(subscriptions, list):
                sub_id = subscriptions[0].get("id") or ""

            domain = classify_academic_domain(title)

            book = PearsonBook(
                id=b_id,
                title=title,
                author=author,
                isbn=isbn,
                book_type=b_type,
                page_count=page_count,
                subscription_id=sub_id,
                domain=domain,
                cover_url=cover,
                ingestion_tier="deep",
            )
            books.append(book)

        return cls(books=books)

    @classmethod
    def load_from_file(cls, path: str | Path) -> PearsonCatalog:
        """Load normalized catalog from JSON manifest."""
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(f"Catalog manifest not found: {p}")
        with open(p) as f:
            data = json.load(f)
        import dataclasses
        valid_fields = {f.name for f in dataclasses.fields(PearsonBook)}
        books = [PearsonBook(**{k: v for k, v in b.items() if k in valid_fields}) for b in data.get("books", [])]
        return cls(books=books)

    def save_to_file(self, path: str | Path) -> None:
        """Persist normalized catalog to JSON manifest."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "total_books": len(self.books),
            "source": "Pearson eLibrary (Institute of Engineering & Management Trust)",
            "books": [b.to_dict() for b in self.books],
        }
        with open(p, "w") as f:
            json.dump(data, f, indent=2)
        logger.info("Saved %d Pearson books to %s", len(self.books), p)

    def find_by_isbn(self, isbn: str) -> PearsonBook | None:
        clean = re.sub(r"[^\d]", "", isbn)
        for b in self.books:
            if re.sub(r"[^\d]", "", b.isbn) == clean:
                return b
        return None

    def find_by_title(self, query: str) -> PearsonBook | None:
        ql = query.lower()
        for b in self.books:
            if ql in b.title.lower() or b.title.lower() in ql:
                return b
        return None

    def list_by_domain(self, domain: str) -> list[PearsonBook]:
        return [b for b in self.books if b.domain.lower() == domain.lower()]
