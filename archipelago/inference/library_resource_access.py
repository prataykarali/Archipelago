"""Safe, student-facing e-resource access responses."""
from __future__ import annotations

from archipelago.inference.library_credentials import (
    E_RESOURCE_CREDENTIALS,
    format_credential_for_response,
    lookup_credential,
)

_FEATURED_RESOURCE_KEYS = (
    "opac",
    "ndli",
    "ieee",
    "scopus",
    "science_direct",
    "springer",
    "ebsco",
    "pearson",
)


def render_resource_access(query: str, resource_key: str = "") -> str:
    """Render portal guidance without exposing institutional credentials."""
    q = (query or "").lower()
    if "scopus" in q and "sciencedirect" in q:
        resources = [
            E_RESOURCE_CREDENTIALS["scopus"],
            E_RESOURCE_CREDENTIALS["science_direct"],
        ]
        return "### Library e-resource access\n\n" + "\n\n".join(
            format_credential_for_response(item) for item in resources
        )
    if "british council" in q and "american library" in q:
        records = [
            E_RESOURCE_CREDENTIALS["british_council"],
            E_RESOURCE_CREDENTIALS["american_library"],
        ]
        return "### Library membership cards\n\n" + "\n\n".join(
            format_credential_for_response(record) for record in records
        )
    resource = E_RESOURCE_CREDENTIALS.get(resource_key) or lookup_credential(query)
    if resource:
        return "### Library e-resource access\n\n" + format_credential_for_response(resource)

    lines = [
        "### Central Library e-resource portals",
        "",
        "Use the relevant institutional portal below; the Central Library desk issues or resets protected credentials.",
        "",
        "| Portal | Access |",
        "| --- | --- |",
    ]
    for key in _FEATURED_RESOURCE_KEYS:
        item = E_RESOURCE_CREDENTIALS[key]
        website = item.get("website", "")
        name = item["name"]
        label = f"[{name}]({website})" if website else name
        lines.append(f"| {label} | {item.get('access', 'Institutional access')} |")
    return "\n".join(lines)
