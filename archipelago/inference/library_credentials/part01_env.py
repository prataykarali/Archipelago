"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

import os
import re
from typing import Any
from . import _deps as _rt  # noqa: F401


def _env(field: str, resource_key: str) -> str:
    """Return env override for a secret field, else ''."""
    env_key = f"ARCHIPELAGO_ERESOURCE_{resource_key.upper()}_{field.upper()}"
    return os.environ.get(env_key, "").strip()


E_RESOURCE_CREDENTIALS: dict[str, dict[str, Any]] = {
    "opac": {
        "name": "IEM/UEM Library Catalogue (OPAC)",
        "type": "Library Catalogue",
        "access": "Student / Faculty Credentials",
        "website": "https://uemk-opac.l2c2.co.in",
        "note": (
            "Sign in with your Emp ID (faculty) or Enrollment No (students). "
            "Password reset and account activation happen at the Central Library desk."
        ),
    },
    "ndli": {
        "name": "National Digital Library of India (NDLI) Club Portal",
        "type": "Digital Library Portal",
        "access": "Registered Members",
        "website": "https://ndl.iitkgp.ac.in/",
        "note": (
            "Use the NDLI Club registration number and passkey issued by the "
            "Central Library. If you do not have these, request them at the desk."
        ),
    },
    "ieee": {
        "name": "IEEE Xplore",
        "type": "Research Database",
        "access": "Username / Password",
        "website": "https://ieeexplore.ieee.org/Xplore/home.jsp",
        "note": "Institutional IEEE Xplore credentials available from Central Library staff.",
    },
    "scopus": {
        "name": "Elsevier Scopus",
        "type": "Bibliographic Database",
        "access": "On-campus IP-based / Institutional Login",
        "website": "https://www.scopus.com/",
        "note": "On-campus IP-based access; off-campus use Central Library's institutional login.",
    },
    "science_direct": {
        "name": "Elsevier ScienceDirect",
        "type": "Full-Text Database",
        "access": "On-campus IP-based / Institutional Login",
        "website": "https://www.sciencedirect.com/",
        "note": "On-campus IP-based access; off-campus use Central Library's institutional login.",
    },
    "springer": {
        "name": "SpringerLink",
        "type": "Publisher Database",
        "access": "Institutional Login",
        "website": "https://link.springer.com/",
        "note": "SpringerLink institutional login — Central Library issues credentials.",
    },
    "ebsco": {
        "name": "EBSCOhost",
        "type": "Research Database",
        "access": "Institutional Login",
        "website": "https://search.ebscohost.com/",
        "note": "EBSCOhost institutional login — ask at the Central Library desk.",
    },
    "jgate": {
        "name": "J-Gate",
        "type": "Journal Gateway",
        "access": "Institutional Login",
        "website": "https://jgateplus.com/search/login/",
        "note": "J-Gate institutional login — Central Library issues user/password.",
    },
    "proquest": {
        "name": "ProQuest",
        "type": "Research Database",
        "access": "Institutional Login",
        "website": "https://www.proquest.com/login",
        "note": "ProQuest institutional login — contact Central Library.",
    },
    "grammarly": {
        "name": "Grammarly",
        "type": "Writing Assistant",
        "access": "Institutional Account",
        "website": "https://www.grammarly.com",
        "note": "Institutional Grammarly account — credentials issued by Central Library.",
    },
    "turnitin": {
        "name": "Turnitin",
        "type": "Plagiarism Checker",
        "access": "Contact Library",
        "website": "https://uemkolkatta.turnitin.com/home/",
        "note": "For Turnitin access, contact the Central Library team.",
    },
    "irins": {
        "name": "IRINS",
        "type": "Research Information System",
        "access": "Public Portal",
        "website": "https://uem-kolkata.irins.org/",
        "note": "IRINS faculty profiles portal (public).",
    },
    "shodhganga": {
        "name": "Shodh Ganga",
        "type": "Thesis Repository",
        "access": "Public Portal",
        "website": "https://shodhganga.inflibnet.ac.in/handle/10603/297435",
        "note": "INFLIBNET Shodhganga theses repository (public).",
    },
    "infed": {
        "name": "INFED",
        "type": "Remote Access / IdP",
        "access": "Emp Id. / Enrollment No.",
        "website": "https://idp.uem.edu.in/",
        "note": "Remote access identity provider — password via Central Library.",
    },
    "pearson": {
        "name": "Pearson eLibrary",
        "type": "E-Book Platform",
        "access": "Institutional Login",
        "website": "https://elibrary.in.pearson.com/",
        "note": (
            "Pearson eLibrary institutional login. Use the credentials issued "
            "by Central Library (staff-side env: ARCHIPELAGO_ERESOURCE_PEARSON_*)."
        ),
    },
    "delnet": {
        "name": "DELNET Digital Library",
        "type": "Consortium Library",
        "access": "Institutional Login",
        "website": "https://discovery1.delnet.in/",
        "note": "DELNET institutional login — Central Library issues user/password.",
    },
    "manupatra": {
        "name": "Manupatra",
        "type": "Legal Database",
        "access": "Institutional Login",
        "website": "https://www.manupatrafast.com/",
        "note": "Manupatra legal research database — credentials via Central Library.",
    },
    "lexis_advance": {
        "name": "Lexis Advance® India / Protege AI",
        "type": "Legal Database",
        "access": "Institutional Login",
        "website": "https://advance.lexis.com/in",
        "note": "Also available at https://protege.in.lexis.com/general-ai.",
    },
    "cambridge_core": {
        "name": "Cambridge Core / Cambridge Law Journal",
        "type": "Academic Publisher Database",
        "access": "IP Based (On-Campus)",
        "website": "https://www.cambridge.org/core/journals/cambridge-law-journal",
        "note": "On-campus IP-based access (no interactive login).",
    },
    "aiu": {
        "name": "Association of Indian Universities eLibrary",
        "type": "E-Library",
        "access": "Institutional Login",
        "website": "https://aiu.refread.com/",
        "note": "AIU eLibrary institutional login — credentials via Central Library.",
    },
    "iei": {
        "name": "The Institution of Engineers (India) [IEI]",
        "type": "Professional Body Portal",
        "access": "Institutional Login",
        "website": "https://www.ieindia.org/WebUI/IEI-Registration.aspx",
        "note": "IEI institutional registration — Central Library issues credentials.",
    },
    "magzter": {
        "name": "Magzter",
        "type": "Digital Magazines",
        "access": "Institutional Login",
        "website": "https://www.magzter.com/",
        "note": "Magzter digital magazine subscription — Central Library account.",
    },
    "efy": {
        "name": "Electronics For You (EFY) ezine",
        "type": "E-Magazine",
        "access": "Institutional Login",
        "website": "https://ezine.efymag.com/loginefy.asp",
        "note": "EFY ezine institutional login — Central Library issues user/password.",
    },
    "india_today": {
        "name": "India Today",
        "type": "E-Magazine",
        "access": "User Id + OTP",
        "website": "https://www.emagpub.com/indiatoday",
        "note": ("Contact the Central Library to get OTP for access."),
    },
    "institutional_repository": {
        "name": "Institutional Repository",
        "type": "Repository",
        "access": "Public Portal",
        "website": "https://uemk.ndl.gov.in/",
        "note": "UEM institutional repository (public).",
    },
    "british_council": {
        "name": "British Council Library Membership",
        "type": "Physical Library Membership",
        "access": "Physical Access Card",
        "card_count": 10,
        "note": "Central Library holds 10 British Council membership access cards. Contact the Library to avail.",
    },
    "american_library": {
        "name": "American Library Membership",
        "type": "Physical Library Membership",
        "access": "Physical Access Card",
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


def lookup_credential(resource_name: str) -> dict[str, Any] | None:
    """Look up metadata for a given resource name or free-text query.

    Returns a copy of the (redacted) metadata dict, or None.
    """
    key = resource_name.strip().lower()
    if not key:
        return None
    if key in E_RESOURCE_CREDENTIALS:
        return dict(E_RESOURCE_CREDENTIALS[key])
    for resource_key_iter, aliases_iter in _RESOURCE_ALIASES.items():
        for alias in aliases_iter:
            if key == alias or alias in key or key in alias:
                return dict(E_RESOURCE_CREDENTIALS[resource_key_iter])
    for resource_key, creds in E_RESOURCE_CREDENTIALS.items():
        name_lower = creds["name"].lower()
        if key in name_lower or name_lower in key:
            return dict(creds)
    return None


_SECRET_FIELD_NAMES: frozenset[str] = frozenset({
    "password",
    "passkey",
    "passkey_alt",
    "username",
    "credential_id",
    "registration_number",
})


def _redacted(_value: Any) -> str:
    return "_(contact Central Library)_"


def format_credential_for_response(credential: dict[str, Any]) -> str:
    """Format resource metadata for student chat.

    The reply NEVER includes plaintext passwords, passkeys, usernames,
    registration numbers, or e-mail identifiers. Only the portal name,
    access type, public URL, card count (for physical memberships), and
    librarian-issued note are rendered.
    """
    name = credential.get("name", "Unknown Resource")
    access = credential.get("access", "")
    note = credential.get("note", "")
    website = credential.get("website", "")

    lines = [
        f"🔐 **{name}**",
        f"   **Access Type**: {access}",
    ]
    if website:
        lines.append(f"   **Website**: {website}")
    if "card_count" in credential:
        lines.append(f"   **Available Cards**: {credential['card_count']}")
    if note:
        lines.append(f"   _Note_: {note}")
    lines.append(
        "   _Credentials:_ ask at the Central Library desk. "
        "Institutional portal usernames and passwords are never shown in chat."
    )

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
