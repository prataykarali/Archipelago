"""Convert model LaTeX / math markup into readable plain-text math."""
from __future__ import annotations

import re

_CMD_MAP = {
    "cdot": "·",
    "times": "×",
    "div": "÷",
    "pm": "±",
    "mp": "∓",
    "leq": "≤",
    "geq": "≥",
    "neq": "≠",
    "approx": "≈",
    "sim": "∼",
    "infty": "∞",
    "sum": "Σ",
    "prod": "Π",
    "int": "∫",
    "partial": "∂",
    "nabla": "∇",
    "alpha": "α",
    "beta": "β",
    "gamma": "γ",
    "delta": "δ",
    "epsilon": "ε",
    "theta": "θ",
    "lambda": "λ",
    "mu": "μ",
    "pi": "π",
    "sigma": "σ",
    "phi": "φ",
    "omega": "ω",
    "ell": "ℓ",
    "rightarrow": "→",
    "leftarrow": "←",
    "Rightarrow": "⇒",
    "Leftarrow": "⇐",
    "to": "→",
    "in": "∈",
    "notin": "∉",
    "subset": "⊂",
    "subseteq": "⊆",
    "forall": "∀",
    "exists": "∃",
    "land": "∧",
    "lor": "∨",
    "neg": "¬",
    "ldots": "…",
    "cdots": "⋯",
}


def fix_math_expressions(text: str) -> str:
    """Rewrite LaTeX-ish math into readable unicode / plain text.

    Keeps meaning (fractions, subscripts, operators) without requiring KaTeX.
    Safe no-op on already-clean prose.
    """
    if not text or "\\" not in text and "$" not in text:
        # Still normalize bare ^ and _ patterns lightly when $ present only —
        # early exit when neither latex nor dollars.
        if not text or ("$" not in text and "^" not in text and "_" not in text):
            return text or ""
        # fall through only for $ / ^ cases below when no backslash
        if "\\" not in text and "$" not in text:
            return text

    out = text

    def _frac(m: re.Match[str]) -> str:
        return f"({m.group(1)})/({m.group(2)})"

    def _cmd(m: re.Match[str]) -> str:
        name = m.group(1)
        return _CMD_MAP.get(name, name)

    # Display / inline math delimiters → keep inner, drop fences
    out = re.sub(r"\$\$([^$]+)\$\$", r" \1 ", out)
    out = re.sub(r"(?<!\$)\$([^$\n]+)\$(?!\$)", r"\1", out)
    out = re.sub(r"\\\((.*?)\\\)", r"\1", out, flags=re.DOTALL)
    out = re.sub(r"\\\[(.*?)\\\]", r"\1", out, flags=re.DOTALL)

    out = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", _frac, out)
    out = re.sub(r"\\sqrt\{([^{}]+)\}", r"√(\1)", out)
    out = re.sub(r"\\mathrm\{([^{}]+)\}", r"\1", out)
    out = re.sub(r"\\mathbf\{([^{}]+)\}", r"\1", out)
    out = re.sub(r"\\text\{([^{}]+)\}", r"\1", out)
    out = re.sub(r"\\operatorname\{([^{}]+)\}", r"\1", out)

    # subscripts / superscripts: x_{i} → x_i , x^{2} → x²-ish plain
    out = re.sub(r"_\{([^{}]+)\}", r"_\1", out)
    out = re.sub(r"\^\{([^{}]+)\}", r"^\1", out)

    out = re.sub(r"\\([a-zA-Z]+)\b", _cmd, out)
    out = out.replace("\\{", "{").replace("\\}", "}")
    out = out.replace("\\_", "_").replace("\\^", "^")
    out = re.sub(r"[{}]", "", out)
    # Collapse leftover double-backslashes from model dumps
    out = out.replace("\\\\", " ")
    out = re.sub(r"\\(?![a-zA-Z])", "", out)  # stray backslashes
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip() if out.strip() == text.strip() else out
