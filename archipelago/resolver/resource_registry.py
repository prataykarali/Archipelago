from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from thefuzz import fuzz
except ImportError:
    fuzz = None
    import difflib

logger = logging.getLogger(__name__)

@dataclass
class ResourceRecord:
    resource_id: str
    title: str = ""
    author: str = ""
    isbn: str = ""
    edition: str = ""
    source: str = ""
    source_id: str = ""
    domain: str = ""
    reader_url: str = ""
    blob_url: str = ""
    resolve_url: str = ""
    hf_repo_id: str = "Prataykarali/Library_books"
    hf_repo_type: str = "dataset"
    hf_revision: str = "main"
    hf_file_path: str = ""
    pearson_subscription_id: str = ""
    pearson_book_id: str = ""
    book_type: str = ""
    page_count: int = 0
    cover_url: str = ""
    status: str = "missing"
    last_verified: str = ""
    error_message: str = ""

    def __post_init__(self):
        if not self.last_verified:
            self.last_verified = datetime.now(timezone.utc).isoformat()


PROMINENT_EBOOKS = [
    {"id": "corpus_book_artificial_intelligence_a_new_synthesis_1998", "title": "Artificial Intelligence: A New Synthesis", "author": "Nils J. Nilsson", "source": "local", "isbn": "9781558604674", "reader_url": "/pdfs/archipelago-books-cs/Artificial_Intelligence_a_new_synthesis_1998/1---Artificial_Intelligence_a_new_synthesis_1998.pdf"},
    {"id": "paper_attention_is_all_you_need_2017", "title": "Attention Is All You Need", "author": "Vaswani et al.", "source": "huggingface", "isbn": "ArXiv-1706.03762", "reader_url": "/read/paper_attention_is_all_you_need_2017", "hf_file_path": "papers/Vaswani2017_Attention_Is_All_You_Need.pdf", "blob_url": "https://huggingface.co/datasets/Prataykarali/Library_books/blob/main/papers/Vaswani2017_Attention_Is_All_You_Need.pdf", "resolve_url": "https://huggingface.co/datasets/Prataykarali/Library_books/resolve/main/papers/Vaswani2017_Attention_Is_All_You_Need.pdf"},
    {"id": "book_math_for_machine_learning_2020", "title": "Mathematics for Machine Learning", "author": "Marc Peter Deisenroth et al.", "source": "huggingface", "isbn": "9781108455145", "reader_url": "/read/book_math_for_machine_learning_2020", "hf_file_path": "textbooks/Deisenroth_Math_For_ML.pdf", "blob_url": "https://huggingface.co/datasets/Prataykarali/Library_books/blob/main/textbooks/Deisenroth_Math_For_ML.pdf", "resolve_url": "https://huggingface.co/datasets/Prataykarali/Library_books/resolve/main/textbooks/Deisenroth_Math_For_ML.pdf"},
    {"id": "paper_goodfellow_2014_gan", "title": "Generative Adversarial Nets", "author": "Ian Goodfellow, Jean Pouget-Abadie, Mehdi Mirza, Bing Xu", "source": "huggingface", "isbn": "ArXiv-1406.2661", "reader_url": "/read/paper_goodfellow_2014_gan", "hf_file_path": "papers/Goodfellow2014_GAN.pdf", "blob_url": "https://huggingface.co/datasets/Prataykarali/Library_books/blob/main/papers/Goodfellow2014_GAN.pdf", "resolve_url": "https://huggingface.co/datasets/Prataykarali/Library_books/resolve/main/papers/Goodfellow2014_GAN.pdf"},
    {"id": "book_speech_and_language_processing_jurafsky", "title": "Speech and Language Processing", "author": "Dan Jurafsky & James H. Martin", "source": "metadata_only", "isbn": "9780131873216", "reader_url": "https://web.stanford.edu/~jurafsky/slp3/"},
    {"id": "ostep_three_easy_pieces", "title": "Operating Systems: Three Easy Pieces (OSTEP)", "author": "Remzi H. Arpaci-Dusseau, Andrea C. Arpaci-Dusseau", "source": "local", "isbn": "9781985086593", "reader_url": "/read/ostep_three_easy_pieces/00_Dialogue.pdf"},
]


class ResourceRegistry:
    def __init__(self, base_dir: Path | None = None):
        if base_dir is None:
            self.base_dir = Path(__file__).resolve().parent.parent.parent
        else:
            self.base_dir = Path(base_dir)
            
        self._resources: dict[str, ResourceRecord] = {}
        self._aliases: dict[str, str] = {}
        self.load_all()

    def load_all(self) -> list[ResourceRecord]:
        self._resources.clear()
        self._aliases.clear()
        
        # 1. Load Prominent eBooks (6 non-Pearson foundational books/papers)
        for data in PROMINENT_EBOOKS:
            rec = ResourceRecord(
                resource_id=data["id"],
                title=data.get("title", ""),
                author=data.get("author", ""),
                source=data.get("source", ""),
                isbn=data.get("isbn", ""),
                reader_url=data.get("reader_url", ""),
                blob_url=data.get("blob_url", ""),
                resolve_url=data.get("resolve_url", ""),
                hf_file_path=data.get("hf_file_path", ""),
                status="resolved" if data.get("source") != "metadata_only" else "missing"
            )
            self._resources[rec.resource_id] = rec

        # Alias for Tanenbaum legacy ID to Pearson book 6e
        self._aliases["book_computer_networks_tanenbaum"] = "0fcd531f-3ba1-495e-9c9e-b43b034b88d9"

        # 2. Load Pearson Books (40 institutional textbooks)
        pearson_path = self.base_dir / "data" / "catalogs" / "pearson_bookshelf.json"
        if pearson_path.exists():
            try:
                with open(pearson_path, "r", encoding="utf-8") as f:
                    pearson_data = json.load(f)
                    
                books = pearson_data if isinstance(pearson_data, list) else pearson_data.get("books", [])
                
                for b in books:
                    raw_id = b.get("id", b.get("uuid", ""))
                    resource_id = raw_id or b.get("isbn", "")
                    r_url = b.get("reader_base_url") or b.get("reader_url") or ""
                    rec = ResourceRecord(
                        resource_id=resource_id,
                        title=b.get("title", ""),
                        author=b.get("author", b.get("authors", "")),
                        isbn=b.get("isbn", ""),
                        edition=b.get("edition", ""),
                        source="pearson",
                        source_id=raw_id,
                        domain=b.get("domain", ""),
                        reader_url=r_url,
                        pearson_subscription_id=b.get("subscription_id", ""),
                        pearson_book_id=raw_id,
                        book_type=b.get("book_type", "reflowable"),
                        page_count=b.get("page_count", 0),
                        cover_url=b.get("cover_url", ""),
                        status="resolved"
                    )
                    self._resources[resource_id] = rec
                    if raw_id:
                        self._aliases[f"pearson_{raw_id}"] = resource_id
            except Exception as e:
                logger.error(f"Error loading Pearson books from {pearson_path}: {e}")
        else:
            logger.warning(f"Pearson catalog not found at {pearson_path}")

        return list(self._resources.values())

    def get_by_id(self, resource_id: str) -> ResourceRecord | None:
        if not resource_id:
            return None
        if resource_id in self._resources:
            return self._resources[resource_id]
        if resource_id in self._aliases:
            target_id = self._aliases[resource_id]
            return self._resources.get(target_id)
        if resource_id.startswith("pearson_"):
            clean_id = resource_id[len("pearson_"):]
            if clean_id in self._resources:
                return self._resources[clean_id]
        return None


    def get_by_isbn(self, isbn: str) -> ResourceRecord | None:
        if not isbn:
            return None
        for r in self._resources.values():
            if r.isbn == isbn:
                return r
        return None

    def fuzzy_search(self, title: str) -> list[ResourceRecord]:
        if not title:
            return []
            
        results = []
        for r in self._resources.values():
            if fuzz is not None:
                score = fuzz.token_sort_ratio(title.lower(), r.title.lower())
            else:
                s = difflib.SequenceMatcher(None, title.lower(), r.title.lower())
                score = int(s.ratio() * 100)
                
            if score > 60:
                results.append((score, r))
                
        results.sort(key=lambda x: x[0], reverse=True)
        return [r for score, r in results]

    def all_resources(self) -> list[ResourceRecord]:
        return list(self._resources.values())

    def reconciliation_report(self) -> dict:
        total = len(self._resources)
        sources: dict[str, int] = {}
        statuses: dict[str, int] = {}
        
        for r in self._resources.values():
            sources[r.source] = sources.get(r.source, 0) + 1
            statuses[r.status] = statuses.get(r.status, 0) + 1
            
        return {
            "total_resources": total,
            "sources": sources,
            "statuses": statuses,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }

    @staticmethod
    def normalize_title(title: str) -> str:
        """
        Normalizes a title by:
        - Converting to lowercase
        - Removing punctuation and standardizing whitespace
        - Standardizing edition formats (e.g., '6/e', '6th edition' -> '6th ed')
        - Normalizing unicode characters
        """
        if not title:
            return ""
            
        # Unicode normalization
        t = unicodedata.normalize('NFKD', title).encode('ASCII', 'ignore').decode('utf-8')
        t = t.lower()
        
        # Standardize edition notation
        t = re.sub(r'\b(\d+)/e\b', r'\g<1>th ed', t)
        t = re.sub(r'\b(\d+)e\b', r'\g<1>th ed', t)
        t = re.sub(r'\b(\d+)st edition\b', r'\g<1>th ed', t)
        t = re.sub(r'\b(\d+)nd edition\b', r'\g<1>th ed', t)
        t = re.sub(r'\b(\d+)rd edition\b', r'\g<1>th ed', t)
        t = re.sub(r'\b(\d+)th edition\b', r'\g<1>th ed', t)
        t = t.replace("sixth edition", "6th ed")
        t = t.replace("fifth edition", "5th ed")
        t = t.replace("fourth edition", "4th ed")
        t = t.replace("third edition", "3th ed")  # Simplification
        t = t.replace("second edition", "2th ed")
        t = t.replace("first edition", "1th ed")

        # Remove punctuation and extra whitespace
        t = re.sub(r'[^\w\s]', ' ', t)
        t = re.sub(r'\s+', ' ', t).strip()
        
        return t

    def detect_duplicates(self) -> list[tuple[ResourceRecord, ResourceRecord]]:
        duplicates: list[tuple[ResourceRecord, ResourceRecord]] = []
        resources = list(self._resources.values())
        
        for i in range(len(resources)):
            for j in range(i + 1, len(resources)):
                r1 = resources[i]
                r2 = resources[j]
                
                # Check ISBN match
                if r1.isbn and r2.isbn and r1.isbn == r2.isbn:
                    duplicates.append((r1, r2))
                    continue
                    
                # Check Normalized Title Match
                nt1 = self.normalize_title(r1.title)
                nt2 = self.normalize_title(r2.title)
                if nt1 and nt2 and nt1 == nt2:
                    # Could add more fuzzy logic here if author also matches
                    duplicates.append((r1, r2))
                    
        return duplicates


_DEFAULT_REGISTRY: ResourceRegistry | None = None

def get_registry() -> ResourceRegistry:
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = ResourceRegistry()
    return _DEFAULT_REGISTRY
