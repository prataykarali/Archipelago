"""Session 7 unit tests: catalog intent routing, renderers, and view-page links."""
import re

from archipelago.inference.routing import _detect_library_intent
from archipelago.inference.library_queries import (
    clean_catalog_topic, clean_journal_query,
)
from archipelago.inference.synthesis_library import (
    render_physical_resources, render_catalog_resources,
    render_resource_availability, render_journal_status,
)
try:
    from archipelago.inference.synthesis_library import (
        view_page_url, inject_view_page_links, _availability_line,
    )
except ImportError:
    # These functions may not exist yet; tests that use them will be skipped
    view_page_url = None
    inject_view_page_links = None
    _availability_line = None


def _intent(query):
    r = _detect_library_intent(query)
    return r["intent"] if r else None


class TestCatalogIntentDetection:
    def test_borrow_book_on_concept(self):
        assert _intent("Can I borrow a book on 3NF?") == "library_resource_lookup"

    def test_checkout_physical_book(self):
        assert _intent("I'm struggling with normalization, can I check out a physical book?") == \
            "library_resource_lookup"

    def test_available_copies(self):
        assert _intent("how many copies of Database Systems are available?") == \
            "library_resource_lookup"

    def test_physical_copy(self):
        assert _intent("is there a physical copy of the math textbook?") == \
            "library_resource_lookup"

    def test_reserve_a_title(self):
        assert _intent("can I reserve the operating systems book?") == \
            "library_resource_lookup"

    def test_latest_journals_available(self):
        assert _intent("Are the latest 2025 ML periodicals available?") == \
            "library_journal_status"

    def test_late_journal_issues(self):
        assert _intent("which journals are late this month?") == "library_journal_status"

    def test_journal_issue_status(self):
        assert _intent("journal issues of IEEE Spectrum") == "library_journal_status"

    def test_subscription_status(self):
        assert _intent("what is the status of our electronics magazine subscriptions?") == \
            "library_journal_status"

    def test_reading_recommendation_not_catalog(self):
        # "what should I read" stays a reading recommendation, not a checkout ask
        assert _intent("what should I read about LoRA?") == "library_books"

    def test_plain_theory_not_catalog(self):
        assert _intent("what is a covariance matrix?") is None

    def test_eresource_login_intent(self):
        assert _intent("what is the sciencedirect login password?") == "library_resources"
        assert _intent("ieee xplore login credentials") == "library_resources"
        assert _intent("how do I access e-resources?") == "library_resources"

    def test_library_times_variants(self):
        # Hours and timing questions use the dedicated library-hours renderer.
        for q in (
            "tell me about library times",
            "tell me about library time",
            "what are the timings of library",
            "tell timing of library",
            "library hours",
            "library times please",
            "when is the library open",
        ):
            assert _intent(q) == "library_hours", q


class TestQueryCleaning:
    def test_clean_catalog_topic_strips_circulation_words(self):
        assert clean_catalog_topic("Can I borrow a book on graph theory?") == "graph theory"

    def test_clean_catalog_topic_struggling(self):
        out = clean_catalog_topic("I'm struggling with 3NF, can I check out a physical book?")
        assert "3nf" in out.lower()
        assert "book" not in out.lower()

    def test_clean_journal_query_strips_journal_words(self):
        out = clean_journal_query("Are the latest 2025 electronics periodicals available?")
        assert out.lower() == "electronics"


class TestViewPageUrl:
    def test_full_url(self):
        url = view_page_url("mml-book.pdf", page=142, highlight="low-rank adaptation")
        assert url.startswith("view-page?doc=mml-book.pdf")
        assert "page=142" in url
        assert "highlight=low-rank%20adaptation" in url

    def test_no_page(self):
        assert "page=" not in view_page_url("doc.pdf")

    def test_empty_doc(self):
        assert view_page_url("") == ""

    def test_doc_id_with_slash_is_encoded(self):
        url = view_page_url("textbooks/mml.pdf", page=3)
        assert "textbooks%2Fmml.pdf" in url


class TestInjectViewPageLinks:
    DOCS = [
        ("textbooks/Deisenroth_Math_For_ML.pdf", "Mathematics for Machine Learning"),
        ("Hu2021_LoRA.pdf", "LoRA: Low-Rank Adaptation of Large Language Models"),
    ]

    def test_notation_gets_link(self):
        text = "PCA reduces dimensionality (Math for ML, PCA, page 317)."
        out = inject_view_page_links(text, known_docs=self.DOCS)
        assert "[View Page 317 of Math for ML](view-page?doc=" in out
        assert "page=317" in out
        assert "highlight=PCA" in out

    def test_unresolvable_book_left_untouched(self):
        text = "See (Cooking Encyclopedia, souffle, page 12) for details."
        out = inject_view_page_links(text, known_docs=self.DOCS)
        assert out == text

    def test_idempotent_on_reprocessing(self):
        text = "PCA reduces dimensionality (Math for ML, PCA, page 317)."
        once = inject_view_page_links(text, known_docs=self.DOCS)
        twice = inject_view_page_links(once, known_docs=self.DOCS)
        assert once.count("[View Page 317") == twice.count("[View Page 317") == 1

    def test_no_docs_no_change(self):
        text = "See (Math for ML, PCA, page 317)."
        assert inject_view_page_links(text, known_docs=[]) == text

    def test_multiple_notations(self):
        text = (
            "Start with (Math for ML, matrix decomposition, page 89) then "
            "read (LoRA, rank decomposition, page 4)."
        )
        out = inject_view_page_links(text, known_docs=self.DOCS)
        assert out.count("[View Page") == 2


class TestAvailabilityLine:
    def test_available(self):
        assert "3 of 5" in _availability_line(5, 3)

    def test_all_out(self):
        assert "checked out" in _availability_line(2, 0)

    def test_untracked(self):
        assert "not tracked" in _availability_line(None, None)

    def test_singular_copy(self):
        assert "copy" in _availability_line(1, 1)


class TestRenderers:
    def test_render_physical_resources(self):
        out = render_physical_resources("Normalization", [{
            "resource_id": "res-1",
            "title": "Database System Concepts",
            "author": "Silberschatz",
            "total_copies": 4,
            "available_copies": 2,
            "barcodes": "IEM0001, IEM0002",
            "doc_id": "dbms-book.pdf",
            "mentions": 7,
        }])
        assert "Database System Concepts" in out
        assert "2 of 4" in out
        assert "IEM0001" in out
        assert "view-page?doc=dbms-book.pdf" in out

    def test_render_physical_resources_empty(self):
        out = render_physical_resources("Quantum Chromodynamics", [])
        assert "No physical resource" in out

    def test_render_catalog_resources(self):
        out = render_catalog_resources("chemistry", [{
            "resource_id": "res-9",
            "title": "Organic Chemistry",
            "author": "Clayden",
            "total_copies": 3,
            "available_copies": 3,
            "barcodes": "IEM0100",
            "subjects": ["CHEMISTRY"],
        }])
        assert "Organic Chemistry" in out
        assert "CHEMISTRY" in out

    def test_render_resource_availability_periodical_hint(self):
        out = render_resource_availability({
            "resource_id": "res-2",
            "title": "IEEE Spectrum",
            "total_copies": 1,
            "available_copies": 1,
            "is_periodical": True,
        })
        assert "IEEE Spectrum" in out
        assert "periodical" in out

    def test_render_journal_status_late_only(self):
        out = render_journal_status({
            "matched_by": "subject",
            "name": "ELECTRONICS",
            "only_late": True,
            "issues": [{
                "resource_title": "Electronics For You",
                "issue_id": "efy|12|3|2025-04-01",
                "volume": "12",
                "issue_number": "3",
                "published_date": "2025-04-01",
                "status": "Late",
            }],
        })
        assert "Late issues" in out
        assert "Electronics For You" in out
        assert "**Late**" in out

    def test_render_journal_status_no_late(self):
        out = render_journal_status({
            "matched_by": "subject",
            "name": "ELECTRONICS",
            "only_late": True,
            "issues": [],
        })
        assert "No late issues were reported" in out
        assert "verify the latest receipt feed" in out
