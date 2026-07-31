"""Library Credentials — E-Resource & OPAC Access (SCH-2).

Grounded in ``docs/IEM-UEM e-Resources Login Credentials (1).pdf``.
Direct lookup only — never sent through a language model (prevents leakage / hallucination).
"""
from __future__ import annotations

import re
from typing import Any


# ── SCH-2: E-Resource Credentials Map (from Central Library PDF) ──────────

E_RESOURCE_CREDENTIALS: dict[str, dict[str, Any]] = {
    "opac": {
        "name": "IEM/UEM Library Catalogue (OPAC)",
        "type": "Library Catalogue",
        "access": "Student / Faculty Credentials",
        "website": "https://uemk-opac.l2c2.co.in",
        "credential_id": "Emp. ID / Enrollment No.",
        "username": "Emp. ID / Enrollment No.",
        "password": "Emp. ID / Enrollment No. (default)",
        "note": (
            "Default password format: Enrollment number for students, "
            "Employee ID for faculty members."
        ),
    },
    "ndli": {
        "name": "National Digital Library of India (NDLI) Club Portal",
        "type": "Digital Library Portal",
        "access": "Registered Members",
        "website": "https://ndl.iitkgp.ac.in/",
        "credential_id": "INWBNC4AU95XQTV",
        "registration_number": "INWBNC4AU95XQTV",
        # Primary passkey from docs/IEM-UEM e-Resources Login Credentials PDF.
        "passkey": "aeb28d3c-de60-439a-89b7-8cfed9aa0657",
        # Alternate passkey seen in some eval sheets / older handouts.
        "passkey_alt": "712a6780-24af-47fb-90d2-b9a7200eabc2",
        "note": (
            "Use the NDLI Club Registration Number and Passkey for portal entry. "
            "Primary passkey (e-resources PDF): aeb28d3c-de60-439a-89b7-8cfed9aa0657. "
            "Alternate club passkey on some handouts: 712a6780-24af-47fb-90d2-b9a7200eabc2."
        ),
    },
    "ieee": {
        "name": "IEEE Xplore",
        "type": "Research Database",
        "access": "Username / Password",
        "website": "https://ieeexplore.ieee.org/Xplore/home.jsp",
        "credential_id": "fG8BeaTC",
        "username": "fG8BeaTC",
        "password": "gh8ccws]",
        "note": "Institutional IEEE Xplore credentials from Central Library e-resources guide.",
    },
    "scopus": {
        "name": "Elsevier Scopus",
        "type": "Bibliographic Database",
        "access": "User ID / Password",
        "website": "https://www.scopus.com/",
        "credential_id": "it@iemcal.com",
        "username": "it@iemcal.com",
        "password": "4359789IEMK",
        "note": "On-campus / institutional Scopus access via Central Library credentials.",
    },
    "science_direct": {
        "name": "Elsevier ScienceDirect",
        "type": "Full-Text Database",
        "access": "User ID / Password",
        "website": "https://www.sciencedirect.com/",
        "credential_id": "it@iemcal.com",
        "username": "it@iemcal.com",
        "password": "4359789IEMK",
        "note": "Same institutional credentials as Scopus.",
    },
    "springer": {
        "name": "Springer Link",
        "type": "Publisher Database",
        "access": "Username / Password",
        "website": "https://link.springer.com/",
        "credential_id": "management.library@iem.edu.in",
        "username": "management.library@iem.edu.in",
        "password": "Iemklib@2026",
        "note": "Springer Link institutional login.",
    },
    "ebsco": {
        "name": "EBSCO Host",
        "type": "Research Database",
        "access": "Username / Password",
        "website": "https://search.ebscohost.com/",
        "credential_id": "iemlibrary",
        "username": "iemlibrary",
        "password": "library@2019",
        "note": "EBSCO Host institutional login.",
    },
    "jgate": {
        "name": "J-Gate",
        "type": "Journal Gateway",
        "access": "Username / Password",
        "website": "https://jgateplus.com/search/login/",
        "credential_id": "trususer",
        "username": "trususer",
        "password": "Jgate3@2024",
        "note": "J-Gate institutional login.",
    },
    "proquest": {
        "name": "ProQuest",
        "type": "Research Database",
        "access": "Username / Password",
        "website": "https://www.proquest.com/login",
        "credential_id": "IEM_LIB",
        "username": "IEM_LIB",
        "password": "ProQuest@1",
        "note": "ProQuest institutional login.",
    },
    "grammarly": {
        "name": "Grammarly",
        "type": "Writing Assistant",
        "access": "User ID / Password",
        "website": "https://www.grammarly.com",
        "credential_id": "pralay.kar@iem.edu.in",
        "username": "pralay.kar@iem.edu.in",
        "password": "Iem@1234",
        "note": "Institutional Grammarly account.",
    },
    "turnitin": {
        "name": "Turnitin",
        "type": "Plagiarism Checker",
        "access": "Contact Library",
        "website": "https://uemkolkatta.turnitin.com/home/",
        "credential_id": "Contact Mr. Raj Nag",
        "note": "For Turnitin access, contact Mr. Raj Nag at the library.",
    },
    "irins": {
        "name": "IRINS",
        "type": "Research Information System",
        "access": "Public Portal",
        "website": "https://uem-kolkata.irins.org/",
        "credential_id": "N/A (public portal)",
        "note": "IRINS faculty profiles portal.",
    },
    "shodhganga": {
        "name": "Shodh Ganga",
        "type": "Thesis Repository",
        "access": "Public Portal",
        "website": "https://shodhganga.inflibnet.ac.in/handle/10603/297435",
        "credential_id": "N/A (public portal)",
        "note": "INFLIBNET Shodhganga theses repository.",
    },
    "infed": {
        "name": "INFED",
        "type": "Remote Access / IdP",
        "access": "Emp Id. / Enrollment No.",
        "website": "https://idp.uem.edu.in/",
        "credential_id": "Emp Id. / Enrollment No.",
        "username": "Emp Id. / Enrollment No.",
        "password": "Contact Library",
        "note": "Remote access identity provider; password via library staff.",
    },
    "pearson": {
        "name": "Pearson eLibrary",
        "type": "E-Book Platform",
        "access": "Username / Password",
        "website": "https://elibrary.in.pearson.com/",
        "credential_id": "library.uemk@uem.edu.in",
        "username": "library.uemk@uem.edu.in",
        "password": "Central-Library@#1",
        "note": "Pearson eLibrary institutional login.",
    },
    "delnet": {
        "name": "DELNET Digital Library",
        "type": "Consortium Library",
        "access": "User Id / Password",
        "website": "https://discovery1.delnet.in/",
        "credential_id": "wbuem",
        "username": "wbuem",
        "password": "uem6490",
        "note": "DELNET institutional login.",
    },
    "manupatra": {
        "name": "Manupatra",
        "type": "Legal Database",
        "access": "User Id / Password",
        "website": "https://www.manupatrafast.com/",
        "credential_id": "TCDMLLaw",
        "username": "TCDMLLaw",
        "password": "legal@1000",
        "note": "Manupatra legal research database.",
    },
    "lexis_advance": {
        "name": "Lexis Advance® India / Protege AI",
        "type": "Legal Database",
        "access": "Username / Password",
        "website": "https://advance.lexis.com/in",
        "credential_id": "library@iem.edu.in",
        "username": "library@iem.edu.in",
        "password": "legal@1000",
        "note": "Also available at https://protege.in.lexis.com/general-ai",
    },
    "cambridge_core": {
        "name": "Cambridge Core / Cambridge Law Journal",
        "type": "Academic Publisher Database",
        "access": "IP Based (On-Campus)",
        "website": "https://www.cambridge.org/core/journals/cambridge-law-journal",
        "credential_id": "IP Based (On-Campus)",
        "note": "The Cambridge Law Journal and Cambridge English Today — on-campus IP-based access.",
    },
    "aiu": {
        "name": "Association of Indian Universities eLibrary",
        "type": "E-Library",
        "access": "User Id / Password",
        "website": "https://aiu.refread.com/",
        "credential_id": "vc@uem.edu.in",
        "username": "vc@uem.edu.in",
        "password": "Librarian@!#2015",
        "note": "AIU eLibrary institutional login.",
    },
    "iei": {
        "name": "The Institution of Engineers (India) [IEI]",
        "type": "Professional Body Portal",
        "access": "User Id / Password",
        "website": "https://www.ieindia.org/WebUI/IEI-Registration.aspx",
        "credential_id": "C10004946",
        "username": "C10004946",
        "password": "C10004946",
        "note": "IEI institutional registration credentials.",
    },
    "magzter": {
        "name": "Magzter",
        "type": "Digital Magazines",
        "access": "User Id / Password",
        "website": "https://www.magzter.com/",
        "credential_id": "arup.kumar.manna92@gmail.com",
        "username": "arup.kumar.manna92@gmail.com",
        "password": "Arup@4",
        "note": "Magzter digital magazine subscription.",
    },
    "efy": {
        "name": "Electronics For You (EFY) ezine",
        "type": "E-Magazine",
        "access": "User Id / Password",
        "website": "https://ezine.efymag.com/loginefy.asp",
        "credential_id": "library.uemk@uem.edu.in",
        "username": "library.uemk@uem.edu.in",
        "password": "E190219",
        "note": "EFY ezine institutional login.",
    },
    "india_today": {
        "name": "India Today",
        "type": "E-Magazine",
        "access": "User Id + OTP",
        "website": "https://www.emagpub.com/indiatoday",
        "credential_id": "library.uemk@uem.edu.in",
        "username": "library.uemk@uem.edu.in",
        "note": "Contact the Library to get OTP for access.",
    },
    "institutional_repository": {
        "name": "Institutional Repository",
        "type": "Repository",
        "access": "Public Portal",
        "website": "https://uemk.ndl.gov.in/",
        "credential_id": "N/A (public portal)",
        "note": "UEM institutional repository.",
    },
    "british_council": {
        "name": "British Council Library Membership",
        "type": "Physical Library Membership",
        "access": "Physical Access Card",
        "credential_id": "10 Membership Access Cards Available",
        "card_count": 10,
        "note": "Central Library holds 10 British Council membership access cards. Contact the Library to avail.",
    },
    "american_library": {
        "name": "American Library Membership",
        "type": "Physical Library Membership",
        "access": "Physical Access Card",
        "credential_id": "5 Membership Access Cards Available",
        "card_count": 5,
        "note": "Central Library holds 5 American Library membership access cards. Contact the Library to avail.",
    },
}

_RESOURCE_ALIASES: dict[str, list[str]] = {
    "opac": [
        "opac", "library catalogue", "iem library", "uem library",
        "iem library catalogue", "uem library catalogue", "catalogue",
        "library catalog", "iem opac", "uem opac", "uemk-opac",
    ],
    "ndli": ["ndli", "national digital library", "ndli club", "ndli portal"],
    "ieee": ["ieee", "ieee xplore", "ieeexplore", "ieee explore"],
    "scopus": ["scopus", "elsevier scopus", "scopus database"],
    "science_direct": ["sciencedirect", "science direct", "elsevier science direct"],
    "springer": ["springer", "springer link", "springerlink"],
    "ebsco": ["ebsco", "ebscohost", "ebsco host"],
    "jgate": ["j-gate", "jgate", "j gate"],
    "proquest": ["proquest", "pro quest"],
    "grammarly": ["grammarly"],
    "turnitin": ["turnitin"],
    "irins": ["irins"],
    "shodhganga": ["shodh ganga", "shodhganga"],
    "infed": ["infed", "idp.uem"],
    "pearson": ["pearson", "pearson elibrary", "pearson e-library"],
    "delnet": ["delnet"],
    "manupatra": ["manupatra"],
    "lexis_advance": [
        "lexis advance", "lexis", "lexis advance india", "protege ai",
        "protegeai", "legal database", "lexisnexis",
    ],
    "cambridge_core": [
        "cambridge core", "cambridge", "cambridge law journal",
        "cambridge university press", "cambridge english today",
    ],
    "aiu": ["aiu", "association of indian universities", "aiu elibrary"],
    "iei": ["iei", "institution of engineers", "ie india"],
    "magzter": ["magzter"],
    "efy": ["efy", "electronics for you", "efy ezine"],
    "india_today": ["india today", "indiatoday"],
    "institutional_repository": ["institutional repository", "uem repository"],
    "british_council": [
        "british council", "british council library", "bc library",
        "physical access card",
    ],
    "american_library": ["american library", "american library membership"],
}


def lookup_credential(resource_name: str) -> dict | None:
    """Look up credentials for a given resource name or free-text query."""
    key = resource_name.strip().lower()

    if key in E_RESOURCE_CREDENTIALS:
        return dict(E_RESOURCE_CREDENTIALS[key])

    for resource_key, aliases in _RESOURCE_ALIASES.items():
        for alias in aliases:
            if key == alias or alias in key or key in alias:
                return dict(E_RESOURCE_CREDENTIALS[resource_key])

    for resource_key, creds in E_RESOURCE_CREDENTIALS.items():
        name_lower = creds["name"].lower()
        if key in name_lower or name_lower in key:
            return dict(creds)

    return None


def format_credential_for_response(credential: dict[str, Any]) -> str:
    """Format credential data into a human-readable response (no LLM)."""
    name = credential.get("name", "Unknown Resource")
    access = credential.get("access", "")
    cred_id = credential.get("credential_id", "")
    note = credential.get("note", "")
    website = credential.get("website", "")

    lines = [
        f"🔐 **{name}**",
        f"   **Access Type**: {access}",
    ]
    if website:
        lines.append(f"   **Website**: {website}")
    if cred_id:
        lines.append(f"   **Credential**: `{cred_id}`")
    if "registration_number" in credential:
        lines.append(f"   **Registration Number**: `{credential['registration_number']}`")
    if "passkey" in credential:
        lines.append(f"   **Passkey**: `{credential['passkey']}`")
    if "passkey_alt" in credential:
        lines.append(f"   **Alternate Passkey**: `{credential['passkey_alt']}`")
    if "username" in credential:
        lines.append(f"   **Username / User ID**: `{credential['username']}`")
    if "password" in credential:
        lines.append(f"   **Password**: `{credential['password']}`")
    if "card_count" in credential:
        lines.append(f"   **Available Cards**: {credential['card_count']}")
    if note:
        lines.append(f"   _Note_: {note}")

    return "\n".join(lines)


_CREDENTIALS_KEYWORDS = re.compile(
    r"\b("
    r"login|log\s+in|credential|password|username|passkey|"
    r"how\s+(?:do\s+i|to|many)\s+(?:access|log|sign\s+in|signin|physical\s+access\s+cards?|cards?)|"
    r"access\s+(?:to|cards?|card)|physical\s+access\s+cards?|membership\s+(?:access\s+)?cards?|"
    r"what\s+(?:is\s+the\s+)?(?:login|credential|password|username|id|passkey)\s+(?:for|to)|"
    r"what\s+(?:login|credentials|password|id|passkey)\s+do\s+i\s+use|"
    r"e-?resource\s+(?:access|credential|login)|"
    r"digital\s+library\s+(?:access|login|credential)|"
    r"remote\s+access|off-?campus\s+access|registration\s+number|"
    r"how\s+many\s+(?:physical\s+)?(?:access\s+)?cards?"
    r")\b",
    re.I,
)

_RESOURCE_NAME_PATTERN = re.compile(
    r"\b("
    r"scopus|elsevier\s+scopus|science\s*direct|"
    r"ndli|national\s+digital\s+library|"
    r"ieee|ieee\s+xplore|"
    r"lexis|protege\s*ai|manupatra|"
    r"efy|electronics\s+for\s+you|"
    r"opac|library\s+(?:catalogue|catalog)|"
    r"cambridge\s+(?:core|law)|"
    r"british\s+council|american\s+library|"
    r"springer|ebsco|j-?gate|proquest|grammarly|turnitin|"
    r"pearson|delnet|magzter|india\s+today|infed|irins|shodh\s*ganga|"
    r"iem\s+library|uem\s+library"
    r")\b",
    re.I,
)


def detect_credentials_query(query: str) -> dict | None:
    """Check if a user query is asking about e-resource credentials."""
    if not query:
        return None

    q_lower = query.lower().strip()

    # Match known credential emails / ids even without "login" keywords
    # (e.g. "Which database uses library@iem.edu.in?").
    for resource_key, creds in E_RESOURCE_CREDENTIALS.items():
        for field in ("credential_id", "username", "passkey", "registration_number"):
            val = str(creds.get(field) or "").strip().lower()
            if val and "@" in val and val in q_lower:
                return {
                    "route": "library_credentials",
                    "resource_key": resource_key,
                    "raw_query": query,
                }

    if not _CREDENTIALS_KEYWORDS.search(q_lower):
        if not re.search(r"\b(login|credential|password|username|id|passkey)\b", q_lower):
            return None

    resource_match = _RESOURCE_NAME_PATTERN.search(q_lower)
    if not resource_match:
        for resource_key, aliases in _RESOURCE_ALIASES.items():
            for alias in aliases:
                if alias in q_lower:
                    return {
                        "route": "library_credentials",
                        "resource_key": resource_key,
                        "raw_query": query,
                    }
        return None

    matched_text = resource_match.group(1).lower()
    for resource_key, aliases in _RESOURCE_ALIASES.items():
        for alias in aliases:
            if matched_text in alias or alias in matched_text:
                return {
                    "route": "library_credentials",
                    "resource_key": resource_key,
                    "raw_query": query,
                }

    return None
