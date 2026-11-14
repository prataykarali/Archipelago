"""Unit and negative tests for Phase 2-9 multi-source scholarly discovery & Google Scholar import."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from unittest.mock import MagicMock

from archipelago.scholarly.contracts.okf_models import (
    PaperIdentifiers,
    PaperRecord,
    ProvenancePointer,
)
from archipelago.scholarly.discovery.biomed_sources import (
    fetch_orcid_record,
    search_europe_pmc,
    search_pubmed,
)
from archipelago.scholarly.discovery.canonicalizer import Canonicalizer
from archipelago.scholarly.discovery.extended_sources import (
    fetch_opencitations_for_dois,
    search_datacite,
    search_dblp,
    search_openaire,
)
from archipelago.scholarly.discovery.provider_selector import classify_domain, select_providers
from archipelago.scholarly.discovery.scholar_import import (
    USER_IMPORT_SOURCE_TYPE,
    build_google_scholar_link,
    import_scholar_citations,
)


def _mock_resp(status_code: int, payload: object = None, text: str = "", content_type: str = "application/json") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = {"content-type": content_type}
    if payload is not None:
        raw = json.dumps(payload).encode("utf-8")
        resp.content = raw
        resp.text = raw.decode("utf-8")
        resp.json.return_value = payload
    else:
        resp.content = text.encode("utf-8")
        resp.text = text
    resp.raise_for_status = MagicMock()
    return resp


def test_domain_provider_selection_and_skip_reasons() -> None:
    assert classify_domain("graph neural networks") == "ai_cs"
    assert classify_domain("biomedical ai for radiology") == "biomedical"
    assert classify_domain("research datasets for speech recognition") == "datasets_software"

    biomed = select_providers("biomedical ai")
    assert biomed["domain"] == "biomedical"
    assert "europe_pmc" in biomed["selected"] and "pubmed" in biomed["selected"]
    assert any(s["source"] == "dblp" and "not_selected_for_domain:biomedical" in s["reason"] for s in biomed["skipped"])


def test_dblp_json_and_anubis_202_gate_detection() -> None:
    sess = MagicMock()
    sess.get.return_value = _mock_resp(
        200,
        {
            "result": {
                "hits": {
                    "hit": [
                        {
                            "info": {
                                "title": "Graph Attention Networks.",
                                "authors": {"author": [{"text": "Petar Velickovic", "@pid": "195/7890"}]},
                                "venue": "ICLR",
                                "year": "2018",
                                "type": "Conference and Workshop Papers",
                                "key": "conf/iclr/VelickovicCCRLB18",
                                "doi": "10.48550/arXiv.1710.10903",
                                "ee": "https://arxiv.org/abs/1710.10903",
                            }
                        }
                    ]
                }
            }
        },
    )
    ok = search_dblp(sess, "graph attention", 5)
    assert ok["status"] == "live"
    assert ok["records"][0]["paper"].identifiers.dblp_key == "conf/iclr/VelickovicCCRLB18"

    sess.get.return_value = _mock_resp(
        202,
        text="<!doctype html><title>Making sure you're not a bot!</title>",
        content_type="text/html",
    )
    blocked = search_dblp(sess, "graph attention", 5)
    assert blocked["status"] == "blocked_bot_challenge"
    assert blocked["records"] == []


def test_openaire_datacite_europe_pmc_pubmed_and_opencitations() -> None:
    sess = MagicMock()
    sess.get.return_value = _mock_resp(
        200,
        {
            "results": [
                {
                    "id": "doi_dedup___::abc",
                    "mainTitle": "OpenAIRE GNN Product",
                    "pids": [{"scheme": "doi", "value": "10.1000/oa1"}],
                    "authors": [{"fullName": "A. Researcher"}],
                    "projects": [{"code": "H2020-123", "title": "EU AI", "funding": [{"shortName": "EC"}]}],
                    "bestAccessRight": {"label": "OPEN"},
                    "publicationDate": "2024-01-15",
                }
            ]
        },
    )
    oa = search_openaire(sess, "gnn", 5)
    assert oa["status"] == "live" and oa["records"][0]["source_metadata"]["grants"][0]["award_id"] == "H2020-123"

    sess.get.return_value = _mock_resp(
        200,
        {
            "data": [
                {
                    "id": "10.5281/zenodo.99999",
                    "attributes": {
                        "doi": "10.5281/zenodo.99999",
                        "titles": [{"title": "Bengali Speech Benchmark Dataset"}],
                        "creators": [{"name": "B. Creator"}],
                        "publisher": "Zenodo",
                        "publicationYear": 2024,
                        "types": {"resourceTypeGeneral": "Dataset"},
                        "relatedIdentifiers": [{"relatedIdentifier": "10.1000/paper1", "relationType": "IsSupplementTo"}],
                    },
                }
            ]
        },
    )
    dc = search_datacite(sess, "bengali speech dataset", 5)
    assert dc["records"][0]["paper"].publication_type == "dataset"
    assert dc["records"][0]["paper"].identifiers.datacite_doi == "10.5281/zenodo.99999"

    sess.get.return_value = _mock_resp(
        200,
        {
            "resultList": {
                "result": [
                    {
                        "pmid": "39000001",
                        "pmcid": "PMC1100001",
                        "doi": "10.1016/j.med.2024.01",
                        "title": "Clinical AI Model.",
                        "isOpenAccess": "Y",
                        "journalTitle": "Med AI",
                        "authorList": {"author": [{"fullName": "Dr. X", "affiliation": "Dept Med"}]},
                    }
                ]
            }
        },
    )
    epmc = search_europe_pmc(sess, "clinical ai", 5)
    assert epmc["records"][0]["paper"].identifiers.pmid == "39000001"

    sess.get.side_effect = [
        _mock_resp(200, {"esearchresult": {"idlist": ["39000001"]}}),
        _mock_resp(
            200,
            {
                "result": {
                    "39000001": {
                        "title": "Clinical AI Model.",
                        "articleids": [{"idtype": "doi", "value": "10.1016/j.med.2024.01"}],
                        "authors": [{"name": "Dr. X"}],
                        "fulljournalname": "Med AI",
                        "pubdate": "2024",
                    }
                }
            },
        ),
    ]
    pm = search_pubmed(sess, "clinical ai", 5)
    assert pm["records"][0]["paper"].identifiers.pmid == "39000001"

    sess.get.side_effect = [_mock_resp(200, [{"count": "42"}]), _mock_resp(429, text="rate limit")]
    oc = fetch_opencitations_for_dois(sess, ["10.1000/a", "10.1000/b"])
    assert oc["10.1000/a"]["count"] == 42
    assert oc["10.1000/b"]["status"] == "rate_limited"


def test_orcid_and_conservative_canonicalizer_no_title_merge() -> None:
    sess = MagicMock()
    sess.get.return_value = _mock_resp(
        200,
        {"name": {"given-names": {"value": "Ada"}, "family-name": {"value": "Lovelace"}}},
    )
    rec = fetch_orcid_record(sess, "0000-0002-1825-0097")
    assert rec and rec["verified_name"] == "Ada Lovelace"

    p1 = {
        "source": "openalex",
        "paper": PaperRecord(title="Same Title Paper", identifiers=PaperIdentifiers(doi="10.1000/one")),
        "provenance": ProvenancePointer(source_type="openalex", artifact_sha256="a"),
        "source_metadata": {},
    }
    p2 = {
        "source": "crossref",
        "paper": PaperRecord(title="Same Title Paper", identifiers=PaperIdentifiers(doi="10.1000/two")),
        "provenance": ProvenancePointer(source_type="crossref", artifact_sha256="b"),
        "source_metadata": {},
    }
    p3 = {
        "source": "pubmed",
        "paper": PaperRecord(title="Same Title Paper", identifiers=PaperIdentifiers(doi="10.1000/one", pmid="12345")),
        "provenance": ProvenancePointer(source_type="pubmed", artifact_sha256="c"),
        "source_metadata": {},
    }
    merged = Canonicalizer().canonicalize_candidates([p1, p2, p3])
    assert len(merged) == 2
    assert merged[0]["paper"].identifiers.pmid == "12345"


def test_google_scholar_import_valid_and_negative_cases() -> None:
    link = build_google_scholar_link("continual learning")
    assert "scholar.google.com/scholar?q=" in link

    bib = """@article{kirkpatrick2017overcoming,
      title={Overcoming catastrophic forgetting in neural networks},
      author={Kirkpatrick, James and Pascanu, Razvan},
      journal={PNAS},
      year={2017},
      doi={10.1073/pnas.1611835114}
    }"""
    res = import_scholar_citations(bib)
    assert res["source_type"] == USER_IMPORT_SOURCE_TYPE
    assert res["imported_count"] == 1
    assert res["records"][0]["doi"] == "10.1073/pnas.1611835114"
    assert res["records"][0]["is_user_imported"] is True

    ris = "TY  - JOUR\nTI  - Retrieval-Augmented Generation\nAU  - Lewis, Patrick\nPY  - 2020\nDO  - 10.5555/rag2020\nER  -"
    ris_res = import_scholar_citations(ris)
    assert ris_res["imported_count"] == 1 and ris_res["records"][0]["year"] == "2020"

    bad = import_scholar_citations("@article{broken, author={No Title}}")
    assert bad["imported_count"] == 0 and "bibtex_missing_title:broken" in bad["errors"]


def test_research_chat_handles_provider_filters_duplicates_and_external_citations() -> None:
    host_dir = str(Path(__file__).resolve().parents[2] / "host_inference")
    if host_dir not in sys.path:
        sys.path.insert(0, host_dir)
    from hostapp.research_run_chat import _answer

    run = {
        "options": {"topic": "graph neural networks"},
        "sources": [{"source": "dblp", "status": "blocked_bot_challenge", "error": "dblp_bot_protection_gate"}],
        "papers": [
            {
                "paper_id": "p1",
                "title": "GNN Paper",
                "doi": "10.1000/gnn",
                "source": "openalex",
                "identifiers": {"arxiv_id": "2401.00001"},
                "authors": [{"name": "Alice"}],
                "provenance": [{"source_type": "openalex"}, {"source_type": "crossref"}],
                "citation_observations": [{"provider": "openalex", "count": 12}, {"provider": "opencitations", "count": 9}],
                "references": [],
            }
        ],
        "author_observations": [],
    }
    assert "GNN Paper" in _answer("Which results came from arXiv?", run, "", "r1", "")
    assert "blocked_bot_challenge" in _answer("Which publications appear in DBLP?", run, "", "r1", "")
    assert "openalex, crossref" in _answer("Are any records duplicated between OpenAlex and Crossref?", run, "", "r1", "").lower() or "crossref, openalex" in _answer("Are any records duplicated between OpenAlex and Crossref?", run, "", "r1", "").lower()
    assert "opencitations: 9" in _answer("Which papers have external verified citations?", run, "", "r1", "")


def test_p1_slm_eligibility_domain_openaire_cleanup_and_chat_filters() -> None:
    from archipelago.scholarly.discovery.extended_sources import (
        clean_openaire_author,
        clean_openaire_title,
    )
    from archipelago.scholarly.intelligence.search import assess_topic_eligibility

    assert classify_domain("Efficient Small Language Models for On-Device and Edge Inference") == "ai_cs"
    ok_edge, _ = assess_topic_eligibility(
        "Efficient Small Language Models for On-Device and Edge Inference",
        "QMC: Efficient SLM Edge Inference via Outlier-Aware Quantization",
        "We deploy small language models on mobile edge devices with INT4 quantization.",
    )
    assert ok_edge is True
    ok_biomed, reason = assess_topic_eligibility(
        "Efficient Small Language Models for On-Device and Edge Inference",
        "Efficient Large Language Models in Biomedicine: A Scoping Review",
        "We review large language models in clinical settings with small sample sizes at the edge of care.",
    )
    assert ok_biomed is False and "missing_central_concepts" in reason

    assert clean_openaire_title("<b>Floe</b>   : Federated &amp; Edge SLM") == "Floe : Federated & Edge SLM"
    assert clean_openaire_author("null Sherva Sheshi Rekha") == "Sherva Sheshi Rekha"
    assert clean_openaire_author("null") is None

    host_dir = str(Path(__file__).resolve().parents[2] / "host_inference")
    if host_dir not in sys.path:
        sys.path.insert(0, host_dir)
    from hostapp.research_run_chat import _answer

    run = {
        "options": {"topic": "Efficient Small Language Models for On-Device and Edge Inference"},
        "sources": [],
        "papers": [
            {
                "paper_id": "p1",
                "title": "QMC: Efficient SLM Edge Inference via Outlier-Aware Quantization",
                "doi": "10.1145/3816440.3818524",
                "abstract": "We achieve low-memory inference on mobile NPUs using INT4 quantization.",
                "topics": ["Quantization"],
                "claims": [],
                "authors": [{"name": "Nilesh Prasad Pandey"}],
                "references": [],
            }
        ],
        "author_observations": [],
    }
    q_ans = _answer("Which papers discuss quantization?", run, "", "r1", "")
    assert "[1] QMC:" in q_ans and "exact match" in q_ans
    m_ans = _answer("Which discuss low-memory inference?", run, "", "r1", "")
    assert "[1] QMC:" in m_ans
    none_ans = _answer("Which papers discuss neuromorphic spiking?", run, "", "r1", "")
    assert "No papers in this collection contain explicit evidence" in none_ans
    exp_ans = _answer("Export this research collection to Excel.", run, "", "r1", "")
    assert "14-sheet workbook" in exp_ans
