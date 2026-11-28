"""Deterministic math, scientific guardrail, and claim-support checks for synthesis."""

from __future__ import annotations

from collections.abc import Sequence
import math
import re
from typing import Any

DEFAULT_PAGE_OFFSET_BITS = 12
MIN_PAGE_OFFSET_BITS = 4
MAX_PAGE_OFFSET_BITS = 24
HEX_BASE = 16
SOFTMAX_TOLERANCE = 0.015
MIN_SOFTMAX_ARITY = 2
MIN_PASSAGE_OVERLAP_TOKENS = 1
MAX_GUIDANCE_RULES = 3

CLAIM_STATUS_VERIFIED = "VERIFIED"
CLAIM_STATUS_UNASSESSED = "UNASSESSED"
CLAIM_STATUS_PARTIAL_OR_UNSUPPORTED = "PARTIAL_OR_UNSUPPORTED"
CLAIM_STATUS_INCOMPLETE = "INCOMPLETE_UNVALIDATED"
SOURCE_KIND_VERIFIED_FULL_TEXT = "verified_full_text_passage"

_PAGE_SIZE_RE = re.compile(
    r"\b(?:4\s*kib|4\s*kb|4096\s*-?\s*bytes?|12\s*-?\s*bit\s+(?:page\s+)?offset)\b", re.I
)
_POWER2_PAGE_RE = re.compile(r"\b(\d+)\s*-?\s*bit\s+(?:page\s+)?offset\b", re.I)
_HEX_MAPPING_RE = re.compile(
    r"\b(0x[0-9a-fA-F]{3,16})\b.{0,80}?\b(?:->|→|maps?\s+to|translates?\s+to|becomes?)\b"
    r".{0,40}?\b(0x[0-9a-fA-F]{3,16})\b",
    re.I | re.S,
)
_SOFTMAX_CLAIM_RE = re.compile(
    r"softmax\s*\(\s*[\[\(]?\s*([-+]?\d+(?:\.\d+)?(?:\s*,\s*[-+]?\d+(?:\.\d+)?)+)\s*[\]\)]?\s*\)"
    r"\s*(?:=|≈|~=|is|gives?|yields?)\s*"
    r"[\[\(]?\s*([-+]?\d+(?:\.\d+)?(?:\s*(?:,|/|and)\s*[-+]?\d+(?:\.\d+)?)+)\s*[\]\)]?",
    re.I,
)
_ATTN_VEC_DIM_RE = re.compile(
    r"\b(?:attention\s+vector|a)\s*(?:∈|in|\\in)\s*(?:R|\\mathbb\{R\})\^\{?(\d+)\}?", re.I
)
_CONCAT_DIM_RE = re.compile(
    r"\b(?:concatenated\s+(?:feature|vector|representation)s?|\[Wh_i\s*\|\|\s*Wh_j\])"
    r".{0,40}?(?:(\d+)\s*-?\s*D|dim(?:ension)?\s*(?:of\s*)?(\d+)|(?:∈|in|\\in)\s*(?:R|\\mathbb\{R\})\^\{?(\d+)\}?)",
    re.I,
)
_MALFORMED_CFG_RE = re.compile(
    r"(?:^|[\s(`\"'])([A-Z]\s*[*+]\s*[A-Z])\s*(?:->|→)\s*([A-Z])(?:\b|[\s)`\"'])"
)
_INLINE_CITE_RE = re.compile(r"\[S(\d+)(?::[^\]]+)?\]")
_WORD_RE = re.compile(r"[a-z0-9]{4,}")
_STOPWORDS = frozenset(
    re.findall(
        r"[a-z]+",
        "that this with from into over such their there these those which where when "
        "have been were will would could should about between through using",
    )
)

_GUIDANCE_SPECS: tuple[tuple[str, str], ...] = (
    (
        r"\b(?:gat|graph\s+attention)\b",
        "GAT math check: for Wh_i in R^{F'}, concatenated [Wh_i || Wh_j] has dim 2F', so attention vector a must be in R^{2F'}. Verify any numerical softmax.",
    ),
    (
        r"\b(?:dpo|direct\s+preference\s+optimization)\b",
        "DPO check: DPO eliminates a separate explicit reward model via closed-form Bradley-Terry reparameterization of implicit reward r(x,y) = beta*log(pi/pi_ref) + beta*log Z(x).",
    ),
    (
        r"\b(?:bayes(?:'s)?\s+theorem|bayesian\s+inference|posterior\s+probab)\b",
        "Bayes check: P(H|E) = P(E|H)*P(H)/P(E) with P(E) > 0; never equate P(H|E) with P(E|H) and normalize over hypotheses.",
    ),
    (
        r"\b(?:gaussian\s+mle|maximum\s+likelihood|normal\s+distribution\s+mle)\b",
        "Gaussian MLE check: density has 1/sqrt(2*pi*sigma^2); MLE mean is (1/n) sum x_i and MLE variance divides by n (distinct from unbiased 1/(n-1)).",
    ),
    (
        r"\b(?:kl\s+divergence|kullback[-\s]leibler)\b",
        "KL check: D_KL(P||Q) = sum P(x) log(P(x)/Q(x)) is asymmetric, requires P << Q support, and 1D Gaussian form is log(s2/s1)+(s1^2+(m1-m2)^2)/(2*s2^2)-1/2.",
    ),
    (
        r"\b(?:pca|principal\s+component)\b",
        "PCA check: requires mean-centering before forming the symmetric PSD covariance matrix; repeated eigenvalues yield non-unique eigenvectors.",
    ),
    (
        r"\b(?:svd|singular\s+value\s+decomposition)\b",
        "SVD check: if retrieved passages contain A = U Sigma V^T, synthesize the grounded factorization and factor dimensions rather than abstaining.",
    ),
    (
        r"\b(?:paging|page\s+fault|page\s+table)\b",
        "Paging check: low page-offset bits stay unchanged from VA to PA; hardware MMU/TLB traps on fault while OS resolves it; demand-zero/COW faults avoid disk I/O. Attribute OSTEP examples to OSTEP.",
    ),
    (
        r"\bbase[-\s]and[-\s]bounds\b",
        "Base-and-bounds check: valid virtual addresses satisfy half-open interval 0 <= VA < bounds, with physical_addr = base + VA.",
    ),
    (
        r"\bdijkstra\b",
        "Dijkstra check: explicitly state the mandatory non-negative edge-weight requirement w(u,v) >= 0.",
    ),
    (
        r"\b(?:lalr|lr\s+pars|shift[-\s]?reduce|bottom[-\s]up\s+pars)\b",
        "CFG/LALR check: CFG productions have a single non-terminal on LHS (e.g., T -> T * F, never F * F -> T).",
    ),
    (
        r"\b(?:intermediate\s+representation|compiler\s+ir|ir\s+generation)\b",
        "Compiler pipeline check: include Lexical Analysis -> Syntax Analysis -> Semantic Analysis before IR generation.",
    ),
    (
        r"\b(?:osi|data\s+link|framing|crc|cyclic\s+redundancy)\b",
        "OSI/CRC check: sender order is L7..L3 -> L2 Data Link (framing) -> L1 Physical (bits); CRC performs error detection, not forward error correction.",
    ),
    (
        r"\btcp\b",
        "TCP check: clearly separate connection setup (3-way handshake), receiver flow control (rwnd), and network congestion control (cwnd / AIMD).",
    ),
    (
        r"\b(?:automata|finite\s+automat|context[-\s]free\s+grammar|chomsky)\b",
        "Automata check: regular languages (FA) are a proper subset of context-free languages (CFGs); do not conflate machines with grammars.",
    ),
    (
        r"\b(?:acid|isolation\s+level|serializab|concurrency\s+control)\b",
        "Database isolation check: distinguish Read Uncommitted, Read Committed, Repeatable Read, and Serializable; not all SQL isolation levels guarantee serializability.",
    ),
)
_SCIENTIFIC_GUIDANCE = tuple((re.compile(pat, re.I), msg) for pat, msg in _GUIDANCE_SPECS)

_POST_RULE_SPECS: tuple[tuple[str, str, str, str | None, str], ...] = (
    (
        "dpo_explicit_reward",
        "D14-DEF-030",
        r"\bdpo\b.{0,120}\b(?:trains?|uses?|requires?|relies?\s+on)\s+(?:a\s+)?(?:separate\s+|explicit\s+)reward\s+model\b",
        r"\b(?:without|eliminates?|avoids?|no|not|instead\s+of|rather\s+than)\s+(?:training\s+|using\s+|a\s+)?(?:separate\s+|explicit\s+)?reward\s+model\b",
        "DPO eliminates training a separate explicit reward model via closed-form policy reparameterization.",
    ),
    (
        "bayes_inverse_fallacy",
        "D14-DEF-031",
        r"\b(?:p\s*\(\s*a\s*\|\s*b\s*\)\s*=\s*p\s*\(\s*b\s*\|\s*a\s*\)|p\s*\(\s*h\s*\|\s*e\s*\)\s*=\s*p\s*\(\s*e\s*\|\s*h\s*\)|bayes(?:'s)?\s+theorem\s+(?:ignores?|does\s+not\s+(?:need|use))\s+(?:the\s+)?(?:prior|base\s+rate))",
        r"\b(?:not\s+equal|!=|≠|unless|fallacy|generally\s+different)\b",
        "Bayes' theorem requires weighting by the prior P(H) and normalizing by P(E): P(H|E) = P(E|H)P(H)/P(E); P(H|E) != P(E|H) in general.",
    ),
    (
        "gaussian_mle_unbiased_conflation",
        "D14-DEF-031",
        r"\bmle\s+variance\b.{0,80}(?:1\s*/\s*\(n\s*-\s*1\)|n\s*-\s*1\s+in\s+the\s+denominator)",
        r"\bunbiased\b",
        "Gaussian MLE variance divides by n (1/n), whereas unbiased sample variance divides by (n-1).",
    ),
    (
        "kl_symmetric_claim",
        "D14-DEF-032",
        r"\b(?:kl\s+divergence|kullback[-\s]leibler)\b.{0,80}\b(?:is\s+symmetric|true\s+distance\s+metric|d_?kl\s*\(\s*p\s*\|\|\s*q\s*\)\s*=\s*d_?kl\s*\(\s*q\s*\|\|\s*p\s*\))",
        r"\b(?:not\s+symmetric|asymmetric|non-symmetric|not\s+a\s+(?:true\s+)?(?:distance\s+)?metric)\b",
        "KL divergence D_KL(P||Q) is asymmetric and is not a true distance metric.",
    ),
    (
        "pca_no_centering_or_unique_repeated",
        "D14-DEF-033",
        r"\bpca\b.{0,120}(?:does\s+not\s+require\s+mean[-\s]centering|repeated\s+eigenvalues?\s+(?:still\s+)?(?:have|yield)\s+unique\s+eigenvectors)",
        None,
        "PCA requires mean-centering, and repeated eigenvalues admit any orthonormal basis in their eigenspace.",
    ),
    (
        "base_bounds_inclusive_upper",
        "D14-DEF-036",
        r"\bbase[-\s]and[-\s]bounds\b.{0,160}(?:virtual[_\s]?addr(?:ess)?\s*<=\s*bounds|\[\s*0\s*,\s*bounds\s*\])",
        None,
        "Base-and-bounds validity is the half-open interval 0 <= virtual_addr < bounds (strict inequality).",
    ),
    (
        "paging_all_faults_disk_or_hw_resolves",
        "D14-DEF-035",
        r"(?:every\s+page\s+fault\s+(?:requires?|triggers?)\s+disk\s+i/o|(?:hardware|mmu|tlb)\s+(?:resolves?|handles?)\s+the\s+page\s+fault\s+without\s+os)",
        None,
        "Hardware MMU/TLB traps on a fault while the OS resolves it; demand-zero/COW faults do not require disk I/O.",
    ),
    (
        "dijkstra_negative_weights",
        "D14-DEF-037",
        r"\bdijkstra(?:'s)?\b.{0,100}\b(?:works?\s+(?:correctly\s+)?(?:with|on)\s+negative\s+(?:edge\s+)?weights?|handles?\s+negative\s+(?:edge\s+)?weights?)\b",
        r"\b(?:cannot|does\s+not|fails?|requires?\s+non-negative)\b",
        "Dijkstra's algorithm requires non-negative edge weights (w(u,v) >= 0).",
    ),
    (
        "osi_crc_correction",
        "D14-DEF-040",
        r"\bcrc\b.{0,60}\b(?:performs?\s+error\s+correction|forward\s+error\s+correction|corrects?\s+(?:bit\s+)?errors?)\b",
        r"\b(?:not\s+(?:forward\s+)?error\s+correction|detects?\s+errors?,?\s+not\s+corrects?)\b",
        "CRC performs error detection, not forward error correction.",
    ),
    (
        "tcp_rwnd_cwnd_conflation",
        "D14-DEF-041",
        r"(?:\brwnd\b.{0,50}\bcongestion\s+control\b|\bcwnd\b.{0,50}\breceiver[-\s]driven\s+flow\s+control\b)",
        None,
        "TCP separates receiver flow control (rwnd) from network congestion control (cwnd).",
    ),
    (
        "automata_machine_subset_grammar",
        "D14-DEF-042",
        r"\b(?:finite\s+automata|dfas?|nfas?)\s+(?:are|is)\s+(?:a\s+)?(?:proper\s+)?subset\s+of\s+context[-\s]free\s+grammars?\b",
        None,
        "Regular languages (FA) are a subset of context-free languages (CFGs); machines are not subsets of grammars.",
    ),
    (
        "db_all_isolation_serializable",
        "D14-DEF-043",
        r"\ball\s+(?:sql\s+)?isolation\s+levels?\s+guarantee\s+serializability\b",
        None,
        "Not all SQL isolation levels guarantee serializability; weaker levels permit concurrency anomalies.",
    ),
)
_POST_RULES = tuple(
    (rid, did, re.compile(pat, re.I | re.S), re.compile(anti, re.I) if anti else None, note)
    for rid, did, pat, anti, note in _POST_RULE_SPECS
)


def _verified_citations_map(citations: Sequence[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Index non-withdrawn verified full-text citations by numeric evidence ID."""
    verified: dict[str, dict[str, Any]] = {}
    for idx, cite in enumerate(citations, start=1):
        if not isinstance(cite, dict) or cite.get("withdrawn"):
            continue
        kind = str(cite.get("source_kind") or "")
        if kind and kind != SOURCE_KIND_VERIFIED_FULL_TEXT:
            continue
        eid = str(cite.get("evidence_id") or f"S{idx}").strip().upper()
        num = eid[1:] if eid.startswith("S") and eid[1:].isdigit() else str(idx)
        verified[num] = cite
    return verified


def _claim_result(
    status: str,
    validated: bool,
    reason: str,
    supported: list[str] | None = None,
    unsupported: list[str] | None = None,
    unassessed: list[str] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "status": status,
        "validated": validated,
        "supported_markers": supported or [],
        "unsupported_markers": unsupported or [],
        "reason": reason,
    }
    if unassessed:
        out["unassessed_markers"] = unassessed
    return out


def audit_worked_address_translation(text: str) -> str | None:
    """Return a qualification note if a worked paging example violates offset invariance."""
    if not text:
        return None
    offset_bits: int | None = None
    if _PAGE_SIZE_RE.search(text):
        offset_bits = DEFAULT_PAGE_OFFSET_BITS
    elif m_bits := _POWER2_PAGE_RE.search(text):
        parsed = int(m_bits.group(1))
        if MIN_PAGE_OFFSET_BITS <= parsed <= MAX_PAGE_OFFSET_BITS:
            offset_bits = parsed
    if offset_bits is None:
        return None
    mask = (1 << offset_bits) - 1
    for va_hex, pa_hex in _HEX_MAPPING_RE.findall(text):
        try:
            va_val, pa_val = int(va_hex, HEX_BASE), int(pa_hex, HEX_BASE)
        except ValueError:
            continue
        if (va_val & mask) != (pa_val & mask):
            return (
                f"\n\n> **Numerical consistency check:** Under {offset_bits}-bit page offsets, "
                f"the low {offset_bits} offset bits must stay unchanged across translation "
                f"(`{va_hex}` has offset `{hex(va_val & mask)}`, whereas `{pa_hex}` has `{hex(pa_val & mask)}`)."
            )
    return None


def build_scientific_guard_guidance(
    query: str, *, evidence_backed: bool, citations: Sequence[dict[str, Any]] = ()
) -> str:
    """Return concise domain-general scientific & epistemic synthesis instructions."""
    notes = [g for pat, g in _SCIENTIFIC_GUIDANCE if pat.search(query)][:MAX_GUIDANCE_RULES]
    if not evidence_backed and re.search(
        r"\b(?:paper|study|intrusion\s+detection|nids|authors?|architecture|method)\b", query, re.I
    ):
        notes.append(
            "Unavailable full-text guard: zero verified full-text passages were retrieved. "
            "Do NOT fabricate specific paper architectures, unsupervised/zero-shot claims, or metrics."
        )
    if (
        citations
        and re.search(r"\b(?:svd|singular\s+value)\b", query, re.I)
        and any(
            "singular value" in str(c.get("text_passage") or c.get("passage") or "").lower()
            for c in citations
            if isinstance(c, dict)
        )
    ):
        notes.append(
            "SVD passages are present in retrieved evidence; synthesize A = U Sigma V^T directly."
        )
    return "\n".join(notes)


def strip_unsupported_citations(
    text: str, citations: Sequence[dict[str, Any]]
) -> tuple[str, list[str]]:
    """Strip inline ``[Si]`` markers not backed by verified full-text citations."""
    if not text:
        return "", []
    valid_ids = set(_verified_citations_map(citations))
    stripped: list[str] = []

    def _replace(match: re.Match[str]) -> str:
        if match.group(1) in valid_ids:
            return match.group(0)
        stripped.append(match.group(0))
        return ""

    cleaned = _INLINE_CITE_RE.sub(_replace, text)
    cleaned = re.sub(r" +([.,;:])", r"\1", re.sub(r"[ \t]{2,}", " ", cleaned))
    return cleaned.strip(), stripped


def verify_claim_support(
    text: str,
    citations: Sequence[dict[str, Any]],
    *,
    stream_status: str = "complete",
    assess_passages: bool = True,
) -> dict[str, Any]:
    """Assess inline citation claims against retrieved passages; never fake verification."""
    if stream_status != "complete":
        return _claim_result(CLAIM_STATUS_INCOMPLETE, False, f"stream_status={stream_status}")
    if not assess_passages:
        return _claim_result(CLAIM_STATUS_UNASSESSED, False, "passage_assessment_disabled")

    verified_by_num = _verified_citations_map(citations)
    markers = list(_INLINE_CITE_RE.finditer(text or ""))
    if not markers:
        reason = (
            "no_inline_citation_markers" if verified_by_num else "no_verified_full_text_passages"
        )
        return _claim_result(CLAIM_STATUS_UNASSESSED, False, reason)

    supported: list[str] = []
    unsupported: list[str] = []
    unassessed: list[str] = []
    for match in markers:
        cite = verified_by_num.get(match.group(1))
        if cite is None:
            unsupported.append(match.group(0))
            continue
        passage = str(cite.get("text_passage") or cite.get("passage") or "").lower()
        if not passage:
            unassessed.append(match.group(0))
            continue
        start = max(0, text.rfind(".", 0, match.start()) + 1)
        sent_tokens = {
            t for t in _WORD_RE.findall(text[start : match.start()].lower()) if t not in _STOPWORDS
        }
        pass_tokens = {t for t in _WORD_RE.findall(passage) if t not in _STOPWORDS}
        if not sent_tokens or len(sent_tokens & pass_tokens) >= MIN_PASSAGE_OVERLAP_TOKENS:
            supported.append(match.group(0))
        else:
            unsupported.append(match.group(0))

    if unsupported:
        return _claim_result(
            CLAIM_STATUS_PARTIAL_OR_UNSUPPORTED,
            False,
            "unsupported_citation_markers_detected",
            supported,
            unsupported,
        )
    if unassessed:
        return _claim_result(
            CLAIM_STATUS_UNASSESSED,
            False,
            "citation_passage_text_unavailable",
            supported,
            [],
            unassessed,
        )
    return _claim_result(CLAIM_STATUS_VERIFIED, True, "all_inline_markers_supported", supported)


def _add_issue(issues: list[dict[str, Any]], rule_id: str, defect_id: str, msg: str) -> None:
    issues.append({"rule_id": rule_id, "defect_id": defect_id, "message": msg})


def audit_scientific_response(
    text: str,
    *,
    query: str = "",
    citations: Sequence[dict[str, Any]] = (),
    evidence_backed: bool = False,
) -> dict[str, Any]:
    """Run deterministic math and scientific guardrails on generated prose."""
    if not text:
        return {"passed": True, "issues": [], "qualification_note": None}
    issues: list[dict[str, Any]] = []
    if paging_note := audit_worked_address_translation(text):
        _add_issue(issues, "paging_offset_invariance", "D14-DEF-035", paging_note.strip())
    for match in _SOFTMAX_CLAIM_RE.finditer(text):
        logits = [float(x.strip()) for x in match.group(1).split(",") if x.strip()]
        claimed = [
            float(x.strip())
            for x in re.split(r"\s*(?:,|/|and)\s*", match.group(2).strip())
            if x.strip()
        ]
        if len(logits) >= MIN_SOFTMAX_ARITY and len(logits) == len(claimed):
            max_v = max(logits)
            exps = [math.exp(v - max_v) for v in logits]
            exact = [v / sum(exps) for v in exps]
            if max(abs(e - c) for e, c in zip(exact, claimed, strict=True)) > SOFTMAX_TOLERANCE:
                exp_fmt = ", ".join(f"{v:.3f}" for v in exact)
                _add_issue(
                    issues,
                    "softmax_arithmetic",
                    "D14-DEF-029",
                    f"softmax({match.group(1)}) evaluates to approximately ({exp_fmt}), not ({match.group(2)}).",
                )
    vec_m, cat_m = _ATTN_VEC_DIM_RE.search(text), _CONCAT_DIM_RE.search(text)
    if vec_m and cat_m:
        cat_dim = next((int(g) for g in cat_m.groups() if g), None)
        if cat_dim is not None and int(vec_m.group(1)) != cat_dim:
            _add_issue(
                issues,
                "gat_attention_dimensions",
                "D14-DEF-029",
                f"Attention vector dimension ({vec_m.group(1)}) must match concatenated feature dimension ({cat_dim}).",
            )
    if _MALFORMED_CFG_RE.search(text):
        _add_issue(
            issues,
            "lalr_cfg_production",
            "D14-DEF-038",
            "CFG productions require a single non-terminal on the LHS (e.g., T -> T * F, never F * F -> T).",
        )
    for rule_id, defect_id, pattern, anti_pattern, note in _POST_RULES:
        if pattern.search(text) and not (anti_pattern and anti_pattern.search(text)):
            _add_issue(issues, rule_id, defect_id, note)
    if (
        re.search(r"\b(?:svd|singular\s+value)\b", query, re.I)
        and citations
        and any(
            "singular value" in str(c.get("text_passage") or c.get("passage") or "").lower()
            for c in citations
            if isinstance(c, dict)
        )
        and re.search(
            r"\b(?:formulation|equation|definition)\s+is\s+(?:unavailable|not\s+available|missing)\s+in\s+the\s+corpus\b",
            text,
            re.I,
        )
    ):
        _add_issue(
            issues,
            "svd_false_abstention",
            "D14-DEF-034",
            "SVD source passages are present in retrieved evidence; do not falsely abstain.",
        )
    if (
        re.search(r"\b(?:compiler|intermediate\s+representation|ir\s+generation)\b", query, re.I)
        and re.search(r"\b(?:syntax\s+analysis|parsing)\b", text, re.I)
        and re.search(r"\b(?:intermediate\s+representation|ir\s+generation)\b", text, re.I)
        and not re.search(r"\bsemantic\s+analysis\b", text, re.I)
    ):
        _add_issue(
            issues,
            "compiler_ir_semantic_omission",
            "D14-DEF-039",
            "Compiler IR generation requires Semantic Analysis (type checking / symbol table validation) after parsing.",
        )
    if not evidence_backed and re.search(
        r"\bthe\s+(?:paper|study)\s+(?:proposes?|uses?|introduces?|achieves?)\b.{0,80}\b(?:unsupervised|zero[-\s]shot|architecture|accuracy|f1)\b",
        text,
        re.I | re.S,
    ):
        _add_issue(
            issues,
            "unavailable_paper_fabrication",
            "D14-DEF-044",
            "No verified full-text passages were retrieved for this paper; specific methodology or architecture claims are unsupported.",
        )
    note_str = (
        "\n\n> **Scientific & numerical consistency check:**\n"
        + "\n".join(f"- {i['message']}" for i in issues)
        if issues
        else None
    )
    return {"passed": not issues, "issues": issues, "qualification_note": note_str}
