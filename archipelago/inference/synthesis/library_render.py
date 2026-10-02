"""Auto-split from synthesis.py — do not edit blocks by hand."""
from __future__ import annotations



def render_catalog_stats(query: str) -> str:
    """Render catalog statistics and search results based on query intent."""
    from archipelago.inference import catalog_ops as ops
    ql = (query or "").lower()
    if "journal" in ql:
        return ops.format_journal_totals()
    if any(k in ql for k in ("zero", "0 copy", "not available", "no physical")):
        return ops.format_zero_copy_audit()
    if any(k in ql for k in ("keyword", "containing", "search", "data mining")):
        return ops.format_keyword_title_search(query)
    if any(k in ql for k in ("subject", "highest", "leaderboard", "title count")):
        return ops.format_subject_leaderboard()
    return ops.format_library_holdings_overview(query)


def render_library_info(query: str) -> str:
    """Render authoritative institutional library policy, hours, access, and e-resource info."""
    ql = (query or "").lower()

    # 1. Turnitin access
    if "turnitin" in ql:
        return (
            "**Turnitin Plagiarism Detection Service**:\n"
            "- Central Library provides similarity report checking through Turnitin.\n"
            "- Contact Mr. Raj Nag at the Central Library desk for submission and account verification."
        )

    # 2. Lab manuals / Muskan Xerox
    if "lab manual" in ql or "xerox" in ql or "muskan" in ql:
        return (
            "**Lab Manuals & Reprography Services**:\n"
            "- Location: **B1 LG2.7 (Muskan Xerox)**.\n"
            "- Central Library provides physical copies for reference; photocopies and lab manual reprints "
            "are available at the reprography center in B1 LG2.7."
        )

    # 3. Borrowing rules & Library Cards
    if any(k in ql for k in ("borrow without card", "borrow before card", "request letter", "hod")):
        return (
            "**Temporary Borrowing Before Card Issuance**:\n"
            "- Students who have not yet received their physical card may borrow books by submitting "
            "a formal request letter.\n"
            "- Procedure: Submit a request letter addressed to the Librarian, forwarded and signed by your "
            "Head of Department (HOD).\n"
            "- While awaiting processing, students may freely use the reading room, take photography of reference "
            "materials, or make copies at the Xerox desk."
        )

    if any(k in ql for k in ("first year", "card arrive", "privilege", "without card")):
        return (
            "**Library Privileges Before Card Receipt**:\n"
            "- Students can freely use the reading room in the Central Library.\n"
            "- Permitted activities: quiet study, taking photography of book excerpts, and Xerox services.\n"
            "- To issue physical books, submit a request letter forwarded by your Head of Department (HOD)."
        )

    if any(k in ql for k in ("library card", "enrolment card", "enrollment library card", "enrollment card", "card")):
        return (
            "**Library Card & Enrollment Policy**:\n"
            "- Library cards are generated **automatically** upon admission using your **Enrollment Number**.\n"
            "- There is **no separate application** required for new students to obtain their standard library membership.\n"
            "- Cards are distributed through respective departmental offices or the Central Library circulation desk."
        )

    # 4. Physical layout & access (shelves, register, notices, pyqs)
    if "shelf" in ql or "shelves" in ql or "stack" in ql:
        return (
            "**Central Library Stack Area & Open-Access System**:\n"
            "- The library operates an **open-access** system where students may browse books directly on the shelves.\n"
            "- Main stacks are categorized by subject (AI/ML, Systems, Theory, Mathematics)."
        )

    if "register" in ql or "entry" in ql or "gate" in ql:
        return (
            "**Central Library Gate Entry Register**:\n"
            "- All students and faculty must sign the Entry/Exit Register upon entering and leaving Central Library.\n"
            "- Keep your student ID card ready for inspection at the entry gate."
        )

    if "announcement" in ql or "notice" in ql:
        return (
            "**Central Library Announcements & Notices**:\n"
            "- Official announcements regarding library timings, book return due dates, and new arrivals "
            "are posted on the Central Library notice boards and sent via institutional email."
        )

    if "pyq" in ql or "question" in ql or "exam paper" in ql:
        return (
            "**Previous Year Question Papers (PYQ) & Magazines**:\n"
            "- Previous Year Question Papers (PYQs), periodicals, and bound magazine volumes are maintained "
            "in the Central Library Reference Section for on-site consultation."
        )

    # 5. Catalog stats queries routed here
    if "journal" in ql and ("title" in ql or "count" in ql or "issue" in ql):
        from archipelago.inference import catalog_ops as ops
        return ops.format_journal_totals()

    if "subject" in ql and ("title count" in ql or "highest" in ql or "leaderboard" in ql):
        from archipelago.inference import catalog_ops as ops
        return ops.format_subject_leaderboard()

    if "keyword" in ql or "specified keyword" in ql:
        from archipelago.inference import catalog_ops as ops
        return ops.format_keyword_title_search(query)

    # 6. E-Resources / Portals / OPAC
    if "opac" in ql:
        return (
            "**Central Library OPAC (Online Public Access Catalog)**:\n"
            "- Portal URL: https://uemk-opac.l2c2.co.in\n"
            "- Login Format: Use your Enrollment Number / Emp ID to search catalog availability, reserves, and renewals."
        )

    if any(k in ql for k in ("sciencedirect", "scopus", "elsevier")):
        return (
            "**Elsevier ScienceDirect & Scopus Access**:\n"
            "- Portal: https://www.sciencedirect.com/ and https://www.scopus.com/\n"
            "- Access Type: IP-based access on-campus; institutional login off-campus.\n"
            "- Security Policy: This chat does not display shared passwords. Ask at the Central Library desk for credentials."
        )

    if "ieee" in ql:
        return (
            "**IEEE Xplore Digital Library**:\n"
            "- Portal: https://ieeexplore.ieee.org/\n"
            "- Access Type: IP-based access on-campus; institutional login off-campus.\n"
            "- Security Policy: This chat does not display shared passwords. Ask at the Central Library desk for credentials."
        )

    if "springer" in ql or "springerlink" in ql:
        return (
            "**SpringerLink Online Library**:\n"
            "- Portal: https://link.springer.com/\n"
            "- Access Type: IP-based access on-campus; institutional access off-campus.\n"
            "- Security Policy: This chat does not display shared passwords. Ask at the Central Library desk for credentials."
        )

    if any(k in ql for k in ("e-resource", "eresource", "portal list", "delnet", "j-gate", "ebsco", "ndli")):
        return (
            "**Authorized Institutional E-Resources Portals**:\n"
            "- **Scopus / ScienceDirect**: https://www.sciencedirect.com (IP-based access)\n"
            "- **IEEE Xplore**: https://ieeexplore.ieee.org\n"
            "- **SpringerLink**: https://link.springer.com\n"
            "- **DELNET**: Developing Library Network portal\n"
            "- **NDLI Club**: National Digital Library of India (https://ndl.iitkgp.ac.in)\n"
            "- **J-Gate**: Electronic journal portal\n"
            "- **EBSCOhost**: Research databases\n"
            "- Security Policy: This chat does not display shared passwords. Ask at the Central Library desk for credentials."
        )

    # 7. Operating Hours / Timings / Weekends
    if any(k in ql for k in ("weekend", "saturday", "sunday")):
        return (
            "**Central Library Weekend Schedule**:\n"
            "- The reading hall remains open on Saturdays and Sundays (open 24 hours under the 24 × 7 × 365 policy).\n"
            "- **Notice**: book issue and return services are not available on weekends."
        )

    if any(k in ql for k in ("timing", "hours", "night", "open", "schedule", "break")):
        return (
            "**Central Library Operating Hours & Schedule**:\n"
            "- **Policy**: Open **24 × 7 × 365** (24 hours a day, 7 days a week, 365 days a year).\n"
            "- Students may use the reading hall during night hours and academic breaks.\n"
            "- **Circulation Desk (Book Issue & Return)**:\n"
            "  - **Weekdays (Monday – Friday)**: Full book issue, return, and renewal services available.\n"
            "  - **Weekends (Saturdays and Sundays)**: book issue and return services are not available on weekends.\n"
            "- Online Catalogue: https://uemk-opac.l2c2.co.in"
        )

    # Fallback / generic query
    return (
        "**Central Library Information**:\n"
        "- Open **24 × 7 × 365** (open 24 hours daily for study, including night hours and academic breaks).\n"
        "- **Weekdays**: Circulation desk open for issue and return.\n"
        "- **Weekends**: Reading rooms open; book issue and return services are not available on weekends.\n"
        "- OPAC: https://uemk-opac.l2c2.co.in"
    )
