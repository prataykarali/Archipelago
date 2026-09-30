"""Unit tests for Pearson eLibrary Connector & Catalog Engine."""

from pathlib import Path
import pytest

from archipelago.ingestion.pearson_connector import (
    PearsonBook,
    PearsonCatalog,
    classify_academic_domain,
)


def test_classify_academic_domain():
    assert classify_academic_domain("Artificial Intelligence: A Modern Approach") == "Artificial Intelligence & Machine Learning"
    assert classify_academic_domain("Computer Networks 6/e") == "Computer Networks & Security"
    assert classify_academic_domain("Compilers Principles, Techniques, and Tools") == "Compilers & Algorithms"
    assert classify_academic_domain("Digital Signal Processing, 4e") == "Signal Processing & Mathematics"
    assert classify_academic_domain("Operating Systems: Internals and Design") == "Operating Systems & Architecture"


def test_pearson_book_reader_urls():
    book_pdf = PearsonBook(
        id="book-123",
        title="Test Book PDF",
        author="Author A",
        isbn="9789332526532",
        book_type="pdf",
        page_count=500,
        subscription_id="sub-456",
        domain="Artificial Intelligence & Machine Learning",
    )
    assert "pdfviewer.html" in book_pdf.reader_base_url
    assert "subscriptionId=sub-456" in book_pdf.reader_base_url
    assert "#book/book-123" in book_pdf.reader_base_url
    assert book_pdf.get_page_reader_url(42).endswith("/page/42")

    book_reflow = PearsonBook(
        id="book-789",
        title="Test Reflowable Book",
        author="Author B",
        isbn="9789356063488",
        book_type="reflowable",
        page_count=600,
        subscription_id="sub-456",
        domain="Computer Networks & Security",
    )
    assert "index.html" in book_reflow.reader_base_url
    assert "#book/book-789" in book_reflow.reader_base_url


def test_pearson_catalog_load_and_lookup():
    cat_path = Path("data/catalogs/pearson_bookshelf.json")
    assert cat_path.is_file(), "data/catalogs/pearson_bookshelf.json must exist"

    catalog = PearsonCatalog.load_from_file(cat_path)
    assert len(catalog.books) == 40

    # Test lookup by title
    aima = catalog.find_by_title("Artificial Intelligence")
    assert aima is not None
    assert "Russell" in aima.author or "Norvig" in aima.author or "Stuart" in aima.author
    assert aima.ingestion_tier == "deep"

    # Test lookup by ISBN
    dragon = catalog.find_by_isbn("9789332576216")
    assert dragon is not None
    assert "Compilers" in dragon.title

    # Test domain filtering
    ai_books = catalog.list_by_domain("Artificial Intelligence & Machine Learning")
    assert len(ai_books) >= 3
