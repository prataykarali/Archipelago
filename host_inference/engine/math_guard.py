"""General numerical consistency checks for worked systems examples."""

from __future__ import annotations

import re

_PAGE_SIZE_RE = re.compile(
    r"\b(?:4\s*kib|4\s*kb|4096\s*-?\s*bytes?|12\s*-?\s*bit\s+(?:page\s+)?offset)\b",
    re.I,
)
_POWER2_PAGE_RE = re.compile(r"\b(\d+)\s*-?\s*bit\s+(?:page\s+)?offset\b", re.I)
_HEX_MAPPING_RE = re.compile(
    r"\b(0x[0-9a-fA-F]{3,16})\b.{0,80}?\b(?:->|→|maps?\s+to|translates?\s+to|becomes?)\b"
    r".{0,40}?\b(0x[0-9a-fA-F]{3,16})\b",
    re.I | re.S,
)
DEFAULT_PAGE_OFFSET_BITS = 12


def audit_worked_address_translation(text: str) -> str | None:
    """Return a qualification note if a worked paging example violates offset invariance.

    In paging translation, the low ``k`` offset bits of a virtual address remain
    identical in the resulting physical address. Only checks when the response
    states a page size / offset bit-width and presents a hex VA -> PA mapping.
    """
    if not text:
        return None
    offset_bits: int | None = None
    if _PAGE_SIZE_RE.search(text):
        offset_bits = DEFAULT_PAGE_OFFSET_BITS
    else:
        m_bits = _POWER2_PAGE_RE.search(text)
        if m_bits:
            parsed = int(m_bits.group(1))
            if 4 <= parsed <= 24:
                offset_bits = parsed
    if offset_bits is None:
        return None

    mask = (1 << offset_bits) - 1
    mismatches: list[tuple[str, str, str, str]] = []
    for va_hex, pa_hex in _HEX_MAPPING_RE.findall(text):
        try:
            va_val = int(va_hex, 16)
            pa_val = int(pa_hex, 16)
        except ValueError:
            continue
        if (va_val & mask) != (pa_val & mask):
            mismatches.append(
                (va_hex, pa_hex, hex(va_val & mask), hex(pa_val & mask))
            )
    if not mismatches:
        return None
    va_hex, pa_hex, va_off, pa_off = mismatches[0]
    return (
        "\n\n> **Numerical consistency check:** Under "
        f"{offset_bits}-bit page offsets, the low {offset_bits} offset bits must stay unchanged "
        f"across translation (`{va_hex}` has offset `{va_off}`, whereas `{pa_hex}` has `{pa_off}`)."
    )
