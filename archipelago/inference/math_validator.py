"""Deterministic mathematical and structural verification for scientific synthesis.

Provides pure-Python (with optional SymPy) checks for worked numerical examples,
matrix/vector dimensions, softmax probabilities, Bayes' theorem, Gaussian MLE,
KL divergence, SVD shapes, address translation invariants, and CFG productions.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
import math
import re
from typing import Any

EPISTEMIC_DIRECTLY_SUPPORTED = "DIRECTLY_SUPPORTED"
EPISTEMIC_INDEPENDENTLY_DERIVED = "INDEPENDENTLY_DERIVED_EXAMPLE"
EPISTEMIC_GENERAL_KNOWLEDGE = "GENERAL_MODEL_KNOWLEDGE"
EPISTEMIC_METADATA_ONLY = "METADATA_ONLY"
EPISTEMIC_UNAVAILABLE = "UNAVAILABLE_OR_UNCERTAIN"
EPISTEMIC_STATES: tuple[str, ...] = (
    EPISTEMIC_DIRECTLY_SUPPORTED,
    EPISTEMIC_INDEPENDENTLY_DERIVED,
    EPISTEMIC_GENERAL_KNOWLEDGE,
    EPISTEMIC_METADATA_ONLY,
    EPISTEMIC_UNAVAILABLE,
)

DEFAULT_PROB_TOLERANCE = 0.015
DEFAULT_FLOAT_TOLERANCE = 1e-3
PROB_SUM_TOLERANCE = 1e-3
MIN_PAGE_OFFSET_BITS = 4
MAX_PAGE_OFFSET_BITS = 24
DEFAULT_PAGE_OFFSET_BITS = 12
DEFAULT_CONCAT_COUNT = 2
MIN_SOFTMAX_ARITY = 2
HALF_FACTOR = 0.5
TWO_FACTOR = 2.0
ZERO_TOLERANCE = 1e-12
ROUND_DIGITS_SHORT = 4
ROUND_DIGITS_LONG = 6

_SOFTMAX_CLAIM_RE = re.compile(
    r"softmax\s*\(\s*[\[\(]?\s*([-+]?\d+(?:\.\d+)?(?:\s*,\s*[-+]?\d+(?:\.\d+)?)+)\s*[\]\)]?\s*\)"
    r"\s*(?:=|≈|~=|is|gives?|yields?)\s*"
    r"[\[\(]?\s*([-+]?\d+(?:\.\d+)?(?:\s*(?:,|/|and)\s*[-+]?\d+(?:\.\d+)?)+)\s*[\]\)]?",
    re.I,
)
_CFG_RULE_RE = re.compile(
    r"(?:^|[\s(`\"'])([A-Za-z][A-Za-z0-9_'*+\s]{0,20}?)\s*(?:->|→)\s*([A-Za-z0-9_'*+\-()ε\s]{1,40})"
)
_ATTENTION_VEC_DIM_RE = re.compile(
    r"\b(?:attention\s+vector|a)\s*(?:∈|in|\\in)\s*(?:R|\\mathbb\{R\})\^\{?(\d+)\}?", re.I
)
_CONCAT_DIM_RE = re.compile(
    r"\b(?:concatenated\s+(?:feature|vector|representation)s?|\[Wh_i\s*\|\|\s*Wh_j\])"
    r".{0,40}?(?:(\d+)\s*-?\s*D|dim(?:ension)?\s*(?:of\s*)?(\d+)|(?:∈|in|\\in)\s*(?:R|\\mathbb\{R\})\^\{?(\d+)\}?)",
    re.I,
)
_SINGLE_NONTERMINAL_RE = re.compile(r"^[A-Z][A-Za-z0-9_']*$|^[a-z]+(?:_[a-z]+)*$")


@dataclass(frozen=True)
class MathCheckResult:
    """Structured result for one deterministic mathematical verification check."""

    name: str
    passed: bool
    message: str
    expected: Any = None
    observed: Any = None
    defect_ids: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        """Serialize check result to JSON-safe dictionary."""
        return {
            "name": self.name,
            "passed": self.passed,
            "message": self.message,
            "expected": self.expected,
            "observed": self.observed,
            "defect_ids": list(self.defect_ids),
        }


def _res(
    name: str,
    passed: bool,
    msg: str,
    exp: Any = None,
    obs: Any = None,
    defect: str | None = None,
) -> MathCheckResult:
    return MathCheckResult(name, passed, msg, exp, obs, (defect,) if defect else ())


def compute_softmax(logits: Sequence[float]) -> list[float]:
    """Compute numerically stable softmax probabilities for ``logits``."""
    if not logits:
        raise ValueError("logits must be non-empty")
    max_val = max(logits)
    exps = [math.exp(val - max_val) for val in logits]
    total = sum(exps)
    return [val / total for val in exps]


def verify_softmax(
    logits: Sequence[float],
    claimed: Sequence[float],
    tol: float = DEFAULT_PROB_TOLERANCE,
) -> MathCheckResult:
    """Verify claimed softmax probabilities against exact computation."""
    if not logits or len(logits) != len(claimed):
        return _res(
            "softmax_arithmetic",
            False,
            "Softmax input and output lengths must match and be non-empty.",
            len(logits),
            len(claimed),
            "D14-DEF-029",
        )
    expected = compute_softmax(logits)
    max_err = max(abs(e - c) for e, c in zip(expected, claimed, strict=True))
    passed = max_err <= tol
    r_exp = [round(v, ROUND_DIGITS_SHORT) for v in expected]
    r_obs = [round(v, ROUND_DIGITS_SHORT) for v in claimed]
    msg = (
        f"softmax({list(logits)}) matches {r_exp} within tol={tol}."
        if passed
        else f"Softmax mismatch: expected {r_exp}, got {r_obs} (err {max_err:.4f} > {tol})."
    )
    return _res("softmax_arithmetic", passed, msg, r_exp, r_obs, "D14-DEF-029")


def verify_matvec(
    matrix: Sequence[Sequence[float]],
    vector: Sequence[float],
    claimed: Sequence[float],
    tol: float = DEFAULT_FLOAT_TOLERANCE,
) -> MathCheckResult:
    """Verify matrix-vector multiplication dimensions and arithmetic."""
    if not matrix or not vector:
        return _res(
            "matvec_product", False, "Matrix and vector must be non-empty.", defect="D14-DEF-029"
        )
    cols = len(matrix[0])
    if any(len(row) != cols for row in matrix):
        return _res(
            "matvec_product", False, "Matrix rows have inconsistent lengths.", defect="D14-DEF-029"
        )
    if cols != len(vector):
        return _res(
            "matvec_product",
            False,
            f"Dim mismatch: {cols} cols vs len {len(vector)}.",
            cols,
            len(vector),
            "D14-DEF-029",
        )
    if len(claimed) != len(matrix):
        return _res(
            "matvec_product",
            False,
            f"Output len mismatch: {len(matrix)} vs {len(claimed)}.",
            len(matrix),
            len(claimed),
            "D14-DEF-029",
        )
    expected = [sum(a * b for a, b in zip(row, vector, strict=True)) for row in matrix]
    passed = max(abs(e - c) for e, c in zip(expected, claimed, strict=True)) <= tol
    r_exp = [round(v, ROUND_DIGITS_SHORT) for v in expected]
    msg = (
        "Matrix-vector product verified."
        if passed
        else f"Matrix-vector mismatch: expected {r_exp}, got {list(claimed)}."
    )
    return _res("matvec_product", passed, msg, r_exp, list(claimed), "D14-DEF-029")


def verify_attention_concat_dims(
    feature_dim: int,
    attention_vec_dim: int,
    concat_count: int = DEFAULT_CONCAT_COUNT,
) -> MathCheckResult:
    """Verify GAT attention vector dimension equals ``concat_count * feature_dim``."""
    expected_dim = feature_dim * concat_count
    passed = feature_dim > 0 and attention_vec_dim == expected_dim
    msg = (
        f"Attention vector dim {attention_vec_dim} matches {concat_count}*F'={expected_dim}."
        if passed
        else f"GAT dim mismatch: expected {expected_dim}, got {attention_vec_dim}."
    )
    return _res(
        "gat_attention_dimensions", passed, msg, expected_dim, attention_vec_dim, "D14-DEF-029"
    )


def verify_bayes_posterior(
    prior: float,
    likelihood: float,
    evidence: float,
    claimed: float,
    tol: float = DEFAULT_FLOAT_TOLERANCE,
) -> MathCheckResult:
    """Verify Bayes' theorem P(H|E) = P(E|H) * P(H) / P(E) with probability bounds."""
    if not (0.0 <= prior <= 1.0 and 0.0 <= likelihood <= 1.0):
        return _res("bayes_posterior", False, "Prior and likelihood must lie in [0, 1].")
    if evidence <= ZERO_TOLERANCE or evidence > 1.0:
        return _res("bayes_posterior", False, "Evidence probability P(E) must lie in (0, 1].")
    expected = (likelihood * prior) / evidence
    if expected > 1.0 + PROB_SUM_TOLERANCE:
        return _res(
            "bayes_posterior",
            False,
            "Inconsistent Bayes inputs: P(E|H)*P(H) > P(E).",
            "<= 1.0",
            round(expected, ROUND_DIGITS_LONG),
        )
    passed = abs(expected - claimed) <= tol
    msg = (
        f"Bayes posterior verified: {expected:.6f}."
        if passed
        else f"Bayes mismatch: expected {expected:.6f}, got {claimed:.6f}."
    )
    return _res("bayes_posterior", passed, msg, round(expected, ROUND_DIGITS_LONG), claimed)


def verify_gaussian_mle(
    samples: Sequence[float],
    claimed_mu: float,
    claimed_var: float,
    tol: float = DEFAULT_FLOAT_TOLERANCE,
) -> MathCheckResult:
    """Verify 1D Gaussian MLE mean and variance (1/n denominator, not 1/(n-1))."""
    n = len(samples)
    if n == 0:
        return _res(
            "gaussian_mle", False, "Sample sequence must be non-empty.", defect="D14-DEF-031"
        )
    mu_hat = sum(samples) / n
    var_mle = sum((x - mu_hat) ** 2 for x in samples) / n
    passed = abs(mu_hat - claimed_mu) <= tol and abs(var_mle - claimed_var) <= tol
    msg = (
        f"Gaussian MLE verified: mu={mu_hat:.4f}, var={var_mle:.4f} (1/n)."
        if passed
        else f"Gaussian MLE mismatch: expected mu={mu_hat:.4f}, var={var_mle:.4f} (1/n); got mu={claimed_mu:.4f}, var={claimed_var:.4f}."
    )
    exp = {"mu": round(mu_hat, ROUND_DIGITS_LONG), "var_mle": round(var_mle, ROUND_DIGITS_LONG)}
    return _res(
        "gaussian_mle", passed, msg, exp, {"mu": claimed_mu, "var": claimed_var}, "D14-DEF-031"
    )


def verify_kl_discrete(
    p: Sequence[float],
    q: Sequence[float],
    claimed: float | None = None,
    tol: float = DEFAULT_FLOAT_TOLERANCE,
) -> MathCheckResult:
    """Verify discrete KL(P || Q) including support condition P << Q."""
    if not p or len(p) != len(q):
        return _res(
            "kl_discrete",
            False,
            "P and Q must be non-empty and equal length.",
            defect="D14-DEF-032",
        )
    if abs(sum(p) - 1.0) > PROB_SUM_TOLERANCE or abs(sum(q) - 1.0) > PROB_SUM_TOLERANCE:
        return _res(
            "kl_discrete", False, "Distributions P and Q must each sum to 1.", defect="D14-DEF-032"
        )
    kl_val = 0.0
    for pi, qi in zip(p, q, strict=True):
        if pi < 0 or qi < 0:
            return _res(
                "kl_discrete", False, "Probabilities must be non-negative.", defect="D14-DEF-032"
            )
        if pi > ZERO_TOLERANCE and qi <= ZERO_TOLERANCE:
            kl_val = math.inf
            break
        if pi > ZERO_TOLERANCE:
            kl_val += pi * math.log(pi / qi)
    if claimed is None:
        return _res(
            "kl_discrete", True, f"Computed D_KL(P||Q) = {kl_val}.", kl_val, kl_val, "D14-DEF-032"
        )
    passed = (math.isinf(kl_val) and math.isinf(claimed)) or (
        not math.isinf(kl_val) and abs(kl_val - claimed) <= tol
    )
    msg = (
        f"KL divergence verified: {kl_val:.6f}."
        if passed
        else f"KL mismatch: expected {kl_val}, got {claimed}."
    )
    return _res("kl_discrete", passed, msg, kl_val, claimed, "D14-DEF-032")


def verify_kl_gaussian_1d(
    mu1: float,
    sigma1: float,
    mu2: float,
    sigma2: float,
    claimed: float | None = None,
    tol: float = DEFAULT_FLOAT_TOLERANCE,
) -> MathCheckResult:
    """Verify exact 1D Gaussian closed-form KL(N(mu1, sigma1^2) || N(mu2, sigma2^2))."""
    if sigma1 <= 0 or sigma2 <= 0:
        return _res(
            "kl_gaussian_1d",
            False,
            "Standard deviations must be strictly positive.",
            defect="D14-DEF-032",
        )
    expected = (
        math.log(sigma2 / sigma1)
        + (sigma1 * sigma1 + (mu1 - mu2) ** 2) / (TWO_FACTOR * sigma2 * sigma2)
        - HALF_FACTOR
    )
    rounded = round(expected, ROUND_DIGITS_LONG)
    if claimed is None:
        return _res(
            "kl_gaussian_1d",
            True,
            f"Computed Gaussian KL = {expected:.6f}.",
            rounded,
            rounded,
            "D14-DEF-032",
        )
    passed = abs(expected - claimed) <= tol
    msg = (
        f"Gaussian KL verified: {expected:.6f}."
        if passed
        else f"Gaussian KL mismatch: expected {expected:.6f}, got {claimed:.6f}."
    )
    return _res("kl_gaussian_1d", passed, msg, rounded, claimed, "D14-DEF-032")


def verify_svd_dimensions(
    m: int,
    n: int,
    u_shape: tuple[int, int],
    s_shape: tuple[int, int],
    vt_shape: tuple[int, int],
) -> MathCheckResult:
    """Verify full or reduced SVD factor dimensions for A in R^{m x n}."""
    k = min(m, n)
    full_ok = u_shape == (m, m) and s_shape == (m, n) and vt_shape == (n, n)
    thin_ok = u_shape == (m, k) and s_shape == (k, k) and vt_shape == (k, n)
    passed = m > 0 and n > 0 and (full_ok or thin_ok)
    msg = (
        f"SVD dims valid for A({m}x{n})."
        if passed
        else f"Invalid SVD dims for A({m}x{n}): got {u_shape}, {s_shape}, {vt_shape}."
    )
    exp = {"full": [(m, m), (m, n), (n, n)], "reduced": [(m, k), (k, k), (k, n)]}
    return _res("svd_dimensions", passed, msg, exp, [u_shape, s_shape, vt_shape], "D14-DEF-034")


def verify_base_and_bounds(
    virtual_addr: int,
    base: int,
    bounds: int,
    claimed_valid: bool,
    claimed_pa: int | None = None,
) -> MathCheckResult:
    """Verify base-and-bounds half-open validity [0, bounds) and physical address."""
    expected_valid = 0 <= virtual_addr < bounds
    expected_pa = base + virtual_addr if expected_valid else None
    passed = (claimed_valid == expected_valid) and (
        (not expected_valid) or (claimed_pa is None) or (claimed_pa == expected_pa)
    )
    msg = (
        f"Base-and-bounds verified for VA={virtual_addr} in [0, {bounds})."
        if passed
        else f"Base-and-bounds mismatch for VA={virtual_addr}: expected valid={expected_valid}, PA={expected_pa}."
    )
    return _res(
        "base_and_bounds",
        passed,
        msg,
        {"valid": expected_valid, "pa": expected_pa},
        {"valid": claimed_valid, "pa": claimed_pa},
        "D14-DEF-036",
    )


def verify_paging_offset(
    virtual_addr: int,
    physical_addr: int,
    offset_bits: int = DEFAULT_PAGE_OFFSET_BITS,
) -> MathCheckResult:
    """Verify low ``offset_bits`` page offset invariance between VA and PA."""
    if not (MIN_PAGE_OFFSET_BITS <= offset_bits <= MAX_PAGE_OFFSET_BITS):
        return _res(
            "paging_offset_invariance",
            False,
            f"offset_bits={offset_bits} out of range.",
            defect="D14-DEF-035",
        )
    mask = (1 << offset_bits) - 1
    va_off, pa_off = virtual_addr & mask, physical_addr & mask
    passed = va_off == pa_off
    msg = (
        f"Paging offset preserved ({hex(va_off)})."
        if passed
        else f"Paging offset mismatch: {hex(va_off)} != {hex(pa_off)}."
    )
    return _res("paging_offset_invariance", passed, msg, hex(va_off), hex(pa_off), "D14-DEF-035")


def verify_cfg_production(production: str) -> MathCheckResult:
    """Verify that a CFG production has a single non-terminal on its LHS."""
    parts = re.split(r"->|→", production, maxsplit=1)
    if len(parts) != DEFAULT_CONCAT_COUNT:
        return _res(
            "cfg_production_syntax",
            False,
            f"Production '{production}' missing '->'.",
            defect="D14-DEF-038",
        )
    lhs, rhs = parts[0].strip(), parts[1].strip()
    lhs_ok = bool(_SINGLE_NONTERMINAL_RE.match(lhs)) and bool(rhs)
    msg = (
        f"Valid CFG production '{lhs} -> {rhs}'."
        if lhs_ok
        else f"Malformed CFG production '{production}': LHS '{lhs}' must be a single non-terminal."
    )
    return _res("cfg_production_syntax", lhs_ok, msg, "single non-terminal LHS", lhs, "D14-DEF-038")


def verify_symbolic_equivalence(expr_a: str, expr_b: str) -> MathCheckResult:
    """Verify algebraic equivalence of two expressions using SymPy when installed."""
    try:
        import sympy as sp  # type: ignore[import-untyped]
    except ImportError:
        return _res(
            "symbolic_equivalence", True, "SymPy unavailable; skipped (UNASSESSED).", expr_a, expr_b
        )
    try:
        diff = sp.simplify(sp.sympify(expr_a) - sp.sympify(expr_b))
        passed = bool(diff == 0)
        msg = f"'{expr_a}' == '{expr_b}'." if passed else f"Symbolic diff: {diff}."
        return _res("symbolic_equivalence", passed, msg, 0, str(diff))
    except Exception as exc:
        return _res("symbolic_equivalence", False, f"Symbolic parse error: {exc}", expr_a, expr_b)


def audit_numeric_text(text: str) -> list[MathCheckResult]:
    """Scan generated prose for verifiable softmax, attention-dimension, and CFG claims."""
    results: list[MathCheckResult] = []
    if not text:
        return results
    for match in _SOFTMAX_CLAIM_RE.finditer(text):
        logits = [float(x.strip()) for x in match.group(1).split(",") if x.strip()]
        claimed = [
            float(x.strip())
            for x in re.split(r"\s*(?:,|/|and)\s*", match.group(2).strip())
            if x.strip()
        ]
        if len(logits) >= MIN_SOFTMAX_ARITY and len(logits) == len(claimed):
            results.append(verify_softmax(logits, claimed))
    vec_match, concat_match = _ATTENTION_VEC_DIM_RE.search(text), _CONCAT_DIM_RE.search(text)
    if vec_match and concat_match:
        att_dim = int(vec_match.group(1))
        concat_dim_str = next((g for g in concat_match.groups() if g), "")
        if concat_dim_str and att_dim != int(concat_dim_str):
            concat_dim = int(concat_dim_str)
            results.append(
                _res(
                    "gat_attention_dimensions",
                    False,
                    f"Attention dim ({att_dim}) != concatenated dim ({concat_dim}).",
                    concat_dim,
                    att_dim,
                    "D14-DEF-029",
                )
            )
    for match in _CFG_RULE_RE.finditer(text):
        lhs = match.group(1).strip()
        if any(op in lhs for op in ("*", "+", " ")) and re.search(r"\b[A-Z]\b", lhs):
            results.append(verify_cfg_production(f"{lhs} -> {match.group(2).strip()}"))
    return results
