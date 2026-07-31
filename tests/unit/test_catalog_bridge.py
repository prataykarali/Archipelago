"""
tests/unit/test_catalog_bridge.py
Session 6 exit criteria: link_resource_to_document works, pdf_url is stored,
PROVIDES_TEXT edge is queryable, and auto-linking works.
"""
import os
import sys
import tempfile
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.join(_HERE, "..", "..")
sys.path.insert(0, _ROOT)

import kuzu
from catalog_schema import create_schema
from catalog_ingest import _resource_id_from_title
from catalog_bridge import (
    link_resource_to_document,
    auto_link_resources,
    generate_coverage_report,
)


def _open_fresh_db(tmp_dir: str) -> str:
    db_path = os.path.join(tmp_dir, "test_bridge.db")
    db      = kuzu.Database(db_path)
    conn    = kuzu.Connection(db)
    create_schema(conn)
    
    # Insert a dummy resource
    res_title = "Introduction to Algorithms"
    res_id = _resource_id_from_title(res_title)
    conn.execute(f"""
        CREATE (:Resource {{
            id: '{res_id}',
            title: '{res_title}',
            author: 'Cormen',
            copyright_year: 2022,
            publisher: 'MIT',
            biblionumber: '123',
            total_copies: 5,
            available_copies: 4,
            barcodes: '[]',
            overdue_items: 0,
            is_periodical: false
        }})
    """)
    
    # Insert another dummy resource
    res_title_2 = "Mathematics for Machine Learning"
    res_id_2 = _resource_id_from_title(res_title_2)
    conn.execute(f"""
        CREATE (:Resource {{
            id: '{res_id_2}',
            title: '{res_title_2}',
            author: 'Deisenroth',
            copyright_year: 2020,
            publisher: 'Cambridge',
            biblionumber: '456',
            total_copies: 2,
            available_copies: 2,
            barcodes: '[]',
            overdue_items: 0,
            is_periodical: false
        }})
    """)

    # Insert a dummy document
    doc_id = "intro-to-algorithms.pdf"
    conn.execute(f"""
        CREATE (:Document {{
            id: '{doc_id}',
            doc_hash: 'abc',
            page_count: 100,
            title: 'Intro Algorithms',
            edition: '3rd',
            page_label_map: '{{}}',
            pdf_url: NULL
        }})
    """)

    # Insert another dummy document (for auto-linking)
    doc_id_2 = "mathematics-for-ml.pdf"
    conn.execute(f"""
        CREATE (:Document {{
            id: '{doc_id_2}',
            doc_hash: 'def',
            page_count: 50,
            title: 'Math for ML',
            edition: '1st',
            page_label_map: '{{}}',
            pdf_url: NULL
        }})
    """)
    
    del conn, db
    return db_path


def _query(db_path: str, cypher: str):
    db   = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    return conn.execute(cypher)


class TestCatalogBridge:

    def test_manual_linking_with_external_url(self, tmp_path):
        """link_resource_to_document creates PROVIDES_TEXT edge and stores pdf_url on Document."""
        db_path = _open_fresh_db(str(tmp_path))

        pdf_url = "https://library.example.edu/resources/intro-to-algorithms.pdf"
        success = link_resource_to_document(db_path, "Introduction to Algorithms", "intro-to-algorithms.pdf", pdf_url)
        assert success is True

        # Assert Document.pdf_url updated
        res = _query(db_path, "MATCH (d:Document {id: 'intro-to-algorithms.pdf'}) RETURN d.pdf_url")
        assert res.get_next()[0] == pdf_url

        # Assert PROVIDES_TEXT edge exists and has correct pdf_url property
        res = _query(db_path, "MATCH (r:Resource)-[p:PROVIDES_TEXT]->(d:Document) RETURN r.title, d.id, p.pdf_url")
        row = res.get_next()
        assert row[0] == "Introduction to Algorithms"
        assert row[1] == "intro-to-algorithms.pdf"
        assert row[2] == pdf_url

    def test_auto_linking(self, tmp_path):
        """auto_link_resources fuzzy matches Document filenames to Resource titles and links them."""
        db_path = _open_fresh_db(str(tmp_path))
        
        # Before auto-linking, count PROVIDES_TEXT edges
        res = _query(db_path, "MATCH ()-[p:PROVIDES_TEXT]->() RETURN COUNT(p)")
        assert res.get_next()[0] == 0

        # Run auto-linking
        stats = auto_link_resources(db_path)
        assert stats["linked"] > 0

        # After auto-linking, we should have a link between "Mathematics for Machine Learning" and "mathematics-for-ml.pdf"
        # and possibly "Introduction to Algorithms" and "intro-to-algorithms.pdf"
        res = _query(db_path, "MATCH (r:Resource)-[p:PROVIDES_TEXT]->(d:Document) RETURN r.title, d.id")
        links = []
        while res.has_next():
            links.append(res.get_next())
        
        assert len(links) >= 1
        titles = [link[0] for link in links]
        assert "Mathematics for Machine Learning" in titles

    def test_coverage_report(self, tmp_path):
        """generate_coverage_report outputs correct linked/unlinked resource counts."""
        db_path = _open_fresh_db(str(tmp_path))
        
        # Initial report: 0 of 2 linked
        report = generate_coverage_report(db_path)
        assert "0 of 2 Resources have linked Documents" in report

        # Link one
        link_resource_to_document(db_path, "Introduction to Algorithms", "intro-to-algorithms.pdf")
        
        report = generate_coverage_report(db_path)
        assert "1 of 2 Resources have linked Documents" in report
