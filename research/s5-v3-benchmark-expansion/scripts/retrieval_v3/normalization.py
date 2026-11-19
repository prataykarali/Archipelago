"""Improvements #1 & #2: Token-boundary-aware anchor matching & technical-term normalization."""

from __future__ import annotations

from dataclasses import dataclass
import re

from retrieval_v3.config import DEFAULT_MIN_CONCEPT_NAME_LEN

# Named constants
MIN_PLURAL_STEM_LEN = 4
MIN_IES_STEM_LEN = 4

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_BOUNDARY_TOKEN_RE = re.compile(r"[a-z0-9_]+")
_ALNUM_SPACE_SURFACE_RE = re.compile(r"^[a-z0-9_]+(?: [a-z0-9_]+)*$")
_SEPARATOR_RE = re.compile(r"[-_/]+")
_WHITESPACE_RE = re.compile(r"\s+")

# Curated technical irregular plurals -> singular
IRREGULAR_SINGULARS: dict[str, str] = {
    "matrices": "matrix",
    "vertices": "vertex",
    "indices": "index",
    "axes": "axis",
    "bases": "basis",
    "analyses": "analysis",
    "hypotheses": "hypothesis",
    "criteria": "criterion",
    "phenomena": "phenomenon",
    "automata": "automaton",
    "optima": "optimum",
    "minima": "minimum",
    "maxima": "maximum",
    "spectra": "spectrum",
    "formulae": "formula",
    "radii": "radius",
}

# Suffixes that must not be stripped as simple '-s' plurals
PROTECTED_S_ENDINGS: tuple[str, ...] = (
    "ss",
    "us",
    "is",
    "os",
    "as",
    "ics",
)

# Curated technical alias / acronym -> canonical normalized phrase
CURATED_TECHNICAL_ALIASES: dict[str, tuple[str, ...]] = {
    "svd": ("singular value decomposition",),
    "pca": ("principal component analysis",),
    "sgd": ("stochastic gradient descent",),
    "gd": ("gradient descent",),
    "mle": ("maximum likelihood estimation", "maximum likelihood"),
    "map": ("maximum a posteriori",),
    "kl": ("kullback leibler divergence", "kl divergence"),
    "llm": ("large language model",),
    "fsm": ("finite state machine", "finite automaton"),
    "cfg": ("context free grammar",),
    "rl": ("reinforcement learning",),
    "mlp": ("multilayer perceptron",),
    "rnn": ("recurrent neural network",),
    "cnn": ("convolutional neural network",),
    "gnn": ("graph neural network",),
    "rag": ("retrieval augmented generation",),
    "pdf": ("probability density function",),
    "pmf": ("probability mass function",),
    "cdf": ("cumulative distribution function",),
    "mse": ("mean squared error",),
    "rmse": ("root mean squared error",),
    "mae": ("mean absolute error",),
    "auc": ("area under curve", "roc auc"),
    "svm": ("support vector machine",),
    "gmm": ("gaussian mixture model",),
    "em": ("expectation maximization",),
    "ols": ("ordinary least squares",),
    "backprop": ("backpropagation", "back propagation"),
    "back propagation": ("backpropagation",),
    "eigen value": ("eigenvalue",),
    "eigen vector": ("eigenvector",),
    "dot product": ("inner product",),
    "bayes theorem": ("bayes rule",),
    "chain rule": ("multivariate chain rule",),
    "linear regression": ("ordinary least squares",),
    "softmax": ("softmax regression",),
    "self attention": ("attention mechanism",),
    "whole body control": ("whole body tracking", "humanoid control"),
    "guided generation": ("constrained decoding", "structured generation"),
}

# Common English stopwords excluded from anchor coverage denominator
QUERY_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "between",
        "by",
        "can",
        "do",
        "does",
        "for",
        "from",
        "how",
        "in",
        "into",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "their",
        "these",
        "this",
        "to",
        "used",
        "using",
        "what",
        "when",
        "where",
        "which",
        "why",
        "with",
    }
)


def tokenize_alnum(text: str) -> list[str]:
    """Deterministic lowercase alphanumeric tokenizer."""
    return _TOKEN_RE.findall((text or "").lower())


def singularize_token(token: str) -> str:
    """Apply conservative technical-term singularization to a lowercase token."""
    if token in IRREGULAR_SINGULARS:
        return IRREGULAR_SINGULARS[token]
    if len(token) < MIN_PLURAL_STEM_LEN:
        return token
    if token.endswith("ies") and len(token) >= MIN_IES_STEM_LEN + 1:
        return token[:-3] + "y"
    if any(token.endswith(suffix) for suffix in PROTECTED_S_ENDINGS):
        return token
    if (
        token.endswith("ses")
        or token.endswith("xes")
        or token.endswith("zes")
        or token.endswith("ches")
        or token.endswith("shes")
    ):
        return token[:-2]
    if token.endswith("s"):
        return token[:-1]
    return token


def normalize_technical_text(text: str, *, singularize: bool = True) -> str:
    """Normalize case, hyphens/underscores/slashes, whitespace, and optionally plurals."""
    cleaned = _SEPARATOR_RE.sub(" ", (text or "").lower())
    tokens = tokenize_alnum(cleaned)
    if singularize:
        tokens = [singularize_token(tok) for tok in tokens]
    return " ".join(tokens)


def extract_content_tokens(text: str, *, normalize: bool = True) -> list[str]:
    """Extract non-stopword content tokens for coverage measurement."""
    raw_tokens = tokenize_alnum(_SEPARATOR_RE.sub(" ", (text or "").lower()))
    if normalize:
        raw_tokens = [singularize_token(tok) for tok in raw_tokens]
    return [tok for tok in raw_tokens if tok not in QUERY_STOPWORDS]


@dataclass(frozen=True)
class AnchorMatch:
    """Single matched graph concept anchor inside a query or passage."""

    concept_id: str
    matched_surface: str
    match_kind: str  # "canonical" | "normalized" | "alias" | "substring_legacy"
    matched_tokens: tuple[str, ...]


class ConceptAnchorMatcher:
    """Deterministic matcher supporting token-boundary matching, aliases, and legacy ablation."""

    def __init__(
        self,
        concept_names: dict[str, str],
        *,
        use_boundary_matching: bool = True,
        use_alias_normalization: bool = True,
        custom_aliases: dict[str, tuple[str, ...]] | None = None,
    ) -> None:
        self.concept_names = dict(concept_names)
        self.use_boundary_matching = use_boundary_matching
        self.use_alias_normalization = use_alias_normalization
        self._aliases = dict(CURATED_TECHNICAL_ALIASES)
        if custom_aliases:
            for key, targets in custom_aliases.items():
                self._aliases[normalize_technical_text(key, singularize=False)] = tuple(
                    normalize_technical_text(t, singularize=False) for t in targets
                )

        # Build surface -> list of (concept_id, match_kind)
        self._surface_to_concepts: dict[str, list[tuple[str, str]]] = {}
        self._surface_content_tokens: dict[str, tuple[str, ...]] = {}
        self._token_surfaces: dict[tuple[str, ...], str] = {}
        self._surface_lengths: tuple[int, ...] = ()
        self._special_patterns: dict[str, re.Pattern[str]] = {}
        self._build_surface_index()

    def _register_surface(self, surface: str, concept_id: str, match_kind: str) -> None:
        cleaned = _WHITESPACE_RE.sub(" ", surface.strip().lower())
        if len(cleaned) < DEFAULT_MIN_CONCEPT_NAME_LEN:
            return
        entries = self._surface_to_concepts.setdefault(cleaned, [])
        if not any(cid == concept_id for cid, _ in entries):
            entries.append((concept_id, match_kind))

    def _build_surface_index(self) -> None:
        normalized_name_to_ids: dict[str, list[str]] = {}
        for cid, raw_name in sorted(self.concept_names.items()):
            raw_low = _WHITESPACE_RE.sub(" ", raw_name.strip().lower())
            self._register_surface(raw_low, cid, "canonical")
            if self.use_alias_normalization:
                norm_name = normalize_technical_text(raw_name, singularize=True)
                self._register_surface(norm_name, cid, "normalized")
                normalized_name_to_ids.setdefault(norm_name, []).append(cid)
                # Also register de-hyphenated compound form if multi-word
                if "-" in raw_name:
                    self._register_surface(raw_name.lower().replace("-", ""), cid, "normalized")

        if self.use_alias_normalization:
            for alias_key, targets in sorted(self._aliases.items()):
                norm_alias = normalize_technical_text(alias_key, singularize=True)
                for target in targets:
                    norm_target = normalize_technical_text(target, singularize=True)
                    for cid in normalized_name_to_ids.get(norm_target, []):
                        self._register_surface(norm_alias, cid, "alias")
                    # Bidirectional: if alias_key itself is a concept, register target as alias
                    for cid in normalized_name_to_ids.get(norm_alias, []):
                        self._register_surface(norm_target, cid, "alias")

        lengths: set[int] = set()
        for surface in self._surface_to_concepts:
            self._surface_content_tokens[surface] = tuple(
                extract_content_tokens(surface, normalize=self.use_alias_normalization)
            )
            if self.use_boundary_matching:
                if _ALNUM_SPACE_SURFACE_RE.match(surface):
                    tok_key = tuple(surface.split(" "))
                    self._token_surfaces[tok_key] = surface
                    lengths.add(len(tok_key))
                else:
                    self._special_patterns[surface] = re.compile(
                        rf"(?<![a-z0-9_]){re.escape(surface)}(?![a-z0-9_])"
                    )
        self._surface_lengths = tuple(sorted(lengths))

    def _collect_boundary_surfaces(self, raw_low: str, norm_text: str) -> set[str]:
        matched_surfaces: set[str] = set()
        token_streams: list[list[str]] = [_BOUNDARY_TOKEN_RE.findall(raw_low)]
        if self.use_alias_normalization and norm_text != raw_low:
            token_streams.append(norm_text.split(" "))

        for tokens in token_streams:
            n_toks = len(tokens)
            for gram_len in self._surface_lengths:
                if gram_len > n_toks:
                    break
                for idx in range(n_toks - gram_len + 1):
                    key = tuple(tokens[idx : idx + gram_len])
                    surface = self._token_surfaces.get(key)
                    if surface is not None:
                        matched_surfaces.add(surface)

        for surface, pattern in self._special_patterns.items():
            if pattern.search(raw_low) or (
                self.use_alias_normalization and pattern.search(norm_text)
            ):
                matched_surfaces.add(surface)
        return matched_surfaces

    def match_text(self, text: str) -> list[AnchorMatch]:
        """Match graph concepts in text deterministically."""
        raw_low = _WHITESPACE_RE.sub(" ", (text or "").lower())
        norm_text = (
            normalize_technical_text(text, singularize=True)
            if self.use_alias_normalization
            else raw_low
        )

        if self.use_boundary_matching:
            matched_surfaces = self._collect_boundary_surfaces(raw_low, norm_text)
        else:
            matched_surfaces = {
                surface
                for surface in self._surface_to_concepts
                if surface in raw_low or (self.use_alias_normalization and surface in norm_text)
            }

        best_by_concept: dict[str, AnchorMatch] = {}
        priority = {"canonical": 0, "normalized": 1, "alias": 2, "substring_legacy": 3}

        for surface in matched_surfaces:
            surface_tokens = self._surface_content_tokens[surface]
            for cid, kind in self._surface_to_concepts[surface]:
                effective_kind = kind if self.use_boundary_matching else "substring_legacy"
                candidate = AnchorMatch(
                    concept_id=cid,
                    matched_surface=surface,
                    match_kind=effective_kind,
                    matched_tokens=surface_tokens,
                )
                prev = best_by_concept.get(cid)
                if prev is None or priority[effective_kind] < priority[prev.match_kind]:
                    best_by_concept[cid] = candidate

        return [best_by_concept[cid] for cid in sorted(best_by_concept)]
