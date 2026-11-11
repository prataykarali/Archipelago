"""Allowed extraction schema values and evaluation vocabulary."""

from __future__ import annotations

REQUIRED_KEYS = (
    "concept_name",
    "concept_type",
    "difficulty",
    "summary",
    "prerequisites",
    "unlocks",
    "related_to",
    "tags",
)
VALID_TYPES = frozenset({"core", "technique", "definition", "algorithm", "theorem"})
VALID_DIFFICULTIES = frozenset({"foundational", "intermediate", "advanced"})

# Names that must never become graph nodes. A prior fine-tune turned author
# names into concepts ("Goodfellow"), which pollutes the graph permanently
# because concept nodes are MERGE-d: a bad node cannot be removed without
# rebuilding every downstream edge.
#
# Only a *fully* person-indicating name is flagged. "Goodfellow GAN" is a
# legitimate concept that merely names an author, so a name counts as a person
# only when every token is person-indicating.
PERSON_TOKENS = frozenset(
    {
        "author",
        "authors",
        "et",
        "al",
        "professor",
        "dr",
        "nobel",
        "laureate",
        "ian",
        "geoffrey",
        "yann",
        "andrej",
        "joshua",
        "tim",
        "timothee",
        "goodfellow",
        "pouget",
        "abadie",
        "mirza",
        "bengio",
        "lecun",
        "hinton",
        "vaswani",
        "shazeer",
        "parmar",
        "devlin",
        "chang",
        "lee",
        "toshev",
        "krizhevsky",
        "sutskever",
        "hechtman",
        "srivastava",
        "ho",
        "graphrag",
        "hu",
        "shen",
        "zhu",
        "liu",
        "wang",
        "zhang",
        "chen",
        "li",
        "yang",
        "jurafsky",
        "martin",
        "proakis",
        "manolakis",
        "deisenroth",
        "mohri",
        "silberschatz",
        "galvin",
        "gagne",
        "arpaci",
        "dusseau",
        "stallings",
        "tanenbaum",
        "kernighan",
        "ritchie",
        "thompson",
        "page",
        "karp",
    }
)
# Acronyms whose expansion a fine-tuned model may emit interchangeably with
# the short form. Scored as equal rather than as a miss.
ACRONYM_EXPANSIONS = {
    "lora": "low rank adaptation",
    "sgd": "stochastic gradient descent",
    "bert": "bidirectional encoder representations from transformers",
    "knn": "k nearest neighbors",
    "svm": "support vector machine",
    "adam": "adaptive moment estimation",
    "gnn": "graph neural network",
    "cnn": "convolutional neural network",
    "rnn": "recurrent neural network",
    "rl": "reinforcement learning",
}
