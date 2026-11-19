"""Verified open-license source registry for S5-v3.1 new OA expansion sources."""

from __future__ import annotations

import json
from pathlib import Path

from .constants import (
    PROVENANCE_EPUB_OA_EXTRACTED,
    PROVENANCE_HTML_OA_EXTRACTED,
    PROVENANCE_LATEX_OA_EXTRACTED,
    PROVENANCE_PDF_EXTRACTED,
    RAW_DB_HTML_DIR_REL,
    RAW_DS_TEX_REL,
    RAW_NET_PDF_REL,
    RAW_OS_EPUB_REL,
)
from .extractors import compute_directory_sha256, compute_file_sha256
from .models import SourceLicenseRecord


def build_default_new_oa_source_records(repo_root: Path) -> list[SourceLicenseRecord]:
    """Assemble verified license & provenance records for the 4 new OA sources."""
    os_path = repo_root / RAW_OS_EPUB_REL
    db_dir = repo_root / RAW_DB_HTML_DIR_REL
    net_path = repo_root / RAW_NET_PDF_REL
    ds_path = repo_root / RAW_DS_TEX_REL

    db_dl_manifest = db_dir / "download_manifest.json"
    db_ts = "2026-11-19T11:09:25Z"
    if db_dl_manifest.is_file():
        rows = json.loads(db_dl_manifest.read_text(encoding="utf-8"))
        if rows:
            db_ts = str(rows[0].get("downloaded_at_utc", db_ts))

    return [
        SourceLicenseRecord(
            doc_id="oa_os_001",
            domain="Operating Systems",
            title="Operating System Fundamentals",
            authors="Dr. Umar Khokhar and Dr. Binh Tran (Georgia Gwinnett College)",
            publisher="University System of Georgia / Affordable Learning Georgia (Manifold)",
            version_or_commit="Manifold text 0c25695d updated 2023-06-08T14:30:07.135Z",
            license_id="CC-BY-4.0",
            license_url="https://creativecommons.org/licenses/by/4.0/",
            license_exceptions="None stated on Manifold project metadata.",
            redistribution_permission="open_attribution_required",
            official_url="https://alg.manifoldapp.org/projects/operating-system-fundamentals",
            download_url=(
                "https://cdn.alg.manifoldapp.org/store/text_export/0/c/2/"
                "0c25695d-49e1-4205-8428-d4e0b6e7334a/"
                "ff118083e1213df46a45297f397f74d894dcf01238afda6e6f5835980190c794208130ce9b13878eb44860a0b55682d806646e87d7ff96f94bff463d915ac78e/"
                "asset/d042813cd42c0e7103eb1c0da95e7110.epub"
            ),
            download_timestamp_utc="2026-11-19T11:06:56Z",
            local_raw_path=str(RAW_OS_EPUB_REL),
            source_sha256=compute_file_sha256(os_path) if os_path.is_file() else "",
            source_format="epub",
            provenance_class=PROVENANCE_EPUB_OA_EXTRACTED,
            origin_tier="new_s5v31_oa_expansion",
            retrieval_status="RETRIEVED_VERIFIED" if os_path.is_file() else "MISSING",
            notes="EPUB has no fixed print pages; page_start/page_end recorded as null.",
        ),
        SourceLicenseRecord(
            doc_id="oa_db_001",
            domain="Databases",
            title="Database Design — 2nd Edition",
            authors="Adrienne Watt and Nelson Eng",
            publisher="BCcampus Open Education (mirrored on Engineering LibreTexts)",
            version_or_commit="2nd Edition (2014), Chapters 1.01-1.16",
            license_id="CC-BY-4.0",
            license_url="https://creativecommons.org/licenses/by/4.0/",
            license_exceptions=(
                "CC BY 4.0 except where otherwise noted (figures/appendices excluded; "
                "prose chapters 1.01-1.16 only)."
            ),
            redistribution_permission="open_attribution_required",
            official_url="https://opentextbc.ca/dbdesign01/",
            download_url=(
                "https://eng.libretexts.org/Bookshelves/Computer_Science/"
                "Databases_and_Data_Structures/Database_Design_2e_(Watt)/01%3A_Chapters"
            ),
            download_timestamp_utc=db_ts,
            local_raw_path=str(RAW_DB_HTML_DIR_REL),
            source_sha256=(compute_directory_sha256(db_dir, "ch*.html") if db_dir.is_dir() else ""),
            source_format="html_chapters",
            provenance_class=PROVENANCE_HTML_OA_EXTRACTED,
            origin_tier="new_s5v31_oa_expansion",
            retrieval_status=(
                "RETRIEVED_VIA_OFFICIAL_LIBRETEXTS_MIRROR"
                if db_dir.is_dir() and list(db_dir.glob("ch*.html"))
                else "MISSING"
            ),
            notes=(
                "Primary host https://opentextbc.ca/dbdesign01/ returned HTTP 403 "
                "(Cloudflare anti-bot challenge; NOT bypassed). Retrieved exact CC-BY-4.0 "
                "2nd Edition chapters from Engineering LibreTexts; page_start/page_end null."
            ),
        ),
        SourceLicenseRecord(
            doc_id="oa_net_001",
            domain="Computer Networks",
            title="Computer Networking: Principles, Protocols and Practice",
            authors=(
                "Olivier Bonaventure (with exercises by Vanbever, Van den Schriek, Saucez, Hoerdt)"
            ),
            publisher="Université catholique de Louvain (GitHub obonaventure/cnp3)",
            version_or_commit=(
                "git commit 155b3a61690f282a7c72fe117fcd3b83c7c09035 (Release 9/2011 CNP3.pdf)"
            ),
            license_id="CC-BY-SA-3.0",
            license_url="https://creativecommons.org/licenses/by-sa/3.0/",
            license_exceptions="None stated in book/LICENSE.txt or README.rst.",
            redistribution_permission="share_alike_with_attribution",
            official_url="https://github.com/obonaventure/cnp3",
            download_url="https://github.com/obonaventure/cnp3.git",
            download_timestamp_utc="2026-11-19T11:06:10Z",
            local_raw_path=str(RAW_NET_PDF_REL),
            source_sha256=compute_file_sha256(net_path) if net_path.is_file() else "",
            source_format="pdf",
            provenance_class=PROVENANCE_PDF_EXTRACTED,
            origin_tier="new_s5v31_oa_expansion",
            retrieval_status="RETRIEVED_VERIFIED" if net_path.is_file() else "MISSING",
            notes="282-page PDF; exact 1-based page_start/page_end preserved via PyMuPDF.",
        ),
        SourceLicenseRecord(
            doc_id="oa_ds_001",
            domain="Distributed Systems",
            title="Distributed Systems Lecture Notes (University of Cambridge)",
            authors="Martin Kleppmann",
            publisher=(
                "University of Cambridge, Dept. of Computer Science and Technology "
                "(GitHub ept/dist-sys)"
            ),
            version_or_commit=(
                "git commit b8167ac35e3f529b851460dfc0feacc9e2436c92 (Copyright 2020-2024)"
            ),
            license_id="CC-BY-SA-4.0",
            license_url="https://creativecommons.org/licenses/by-sa/4.0/",
            license_exceptions=("None stated in README.md; strictly excludes mixu/distsysbook."),
            redistribution_permission="share_alike_with_attribution",
            official_url="https://github.com/ept/dist-sys",
            download_url="https://github.com/ept/dist-sys.git",
            download_timestamp_utc="2026-11-19T11:05:36Z",
            local_raw_path=str(RAW_DS_TEX_REL),
            source_sha256=compute_file_sha256(ds_path) if ds_path.is_file() else "",
            source_format="latex",
            provenance_class=PROVENANCE_LATEX_OA_EXTRACTED,
            origin_tier="new_s5v31_oa_expansion",
            retrieval_status="RETRIEVED_VERIFIED" if ds_path.is_file() else "MISSING",
            notes="Raw LaTeX source (dist-sys.tex); page_start/page_end recorded as null.",
        ),
    ]
