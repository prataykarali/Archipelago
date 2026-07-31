from __future__ import annotations

import re

_MAX_INLINE_CITATIONS_REQUESTED: int = 6
_MIN_INLINE_CITATIONS_REQUESTED: int = 3

REPLY_STYLES: list[str] = [
    "Be concise and precise.",
    "Use bullet points where helpful.",
    "Start with the most important fact.",
    "Explain like the student is new to the topic.",
    "Give a one-sentence summary first, then details.",
    "Use numbered steps for procedural answers.",
    "Highlight key terms in bold.",
    "Prefer short paragraphs over long walls of text.",
    "Use analogies to clarify abstract ideas.",
    "Lead with the definition, then examples.",
    "Emphasise practical applications.",
    "Structure as: What, Why, How.",
    "Give the big picture before the details.",
    "Use contrast (A vs B) where relevant.",
    "Summarise prerequisites before the main content.",
    "Frame the answer around a real-world scenario.",
    "Use a Q&A sub-structure within the response.",
    "Start with common misconceptions, then correct them.",
    "Focus on intuition over formalism.",
    "Include a one-line takeaway at the end.",
    "Use sequential 'first, then, finally' structure.",
    "Lean on visual metaphors to aid understanding.",
    "State limitations clearly alongside strengths.",
    "Reference foundational concepts before advanced ones.",
    "Use active voice throughout.",
    "Organise by complexity: simple then advanced.",
    "Tie each point back to the student's query.",
    "Lead with why the topic matters.",
    "Use short sentences for clarity.",
    "Avoid jargon unless defined immediately.",
    "State assumptions explicitly.",
    "Give a historical perspective where relevant.",
    "Use cause-and-effect structure.",
    "Break down acronyms on first use.",
    "Use parallel structure in lists.",
    "Provide a counter-example to deepen understanding.",
    "State what the concept is NOT, then what it IS.",
    "Use a worked numeric example if applicable.",
    "Group related ideas into labelled sections.",
    "Mention open problems or active research if relevant.",
    "Connect to adjacent topics students likely know.",
    "Prefer concrete nouns over vague abstractions.",
    "Use 'for example' to ground every claim.",
    "Give a one-paragraph executive summary first.",
    "Use the student's exact terminology where possible.",
    "Acknowledge ambiguity rather than glossing over it.",
    "Separate 'how it works' from 'when to use it'.",
    "Use a table for comparisons of three or more items.",
    "End with a suggestion for further study.",
    "Start with a motivating problem the concept solves.",
    "Highlight trade-offs explicitly.",
    "Distinguish between theory and practice.",
    "Keep technical depth proportional to the question.",
    "Use 'in other words' to rephrase complex points.",
    "Mention at least one authoritative source.",
    "Adapt vocabulary to an undergraduate CS level.",
    "Explain the intuition, then the mechanics.",
    "Flag any prerequisites the student should review.",
    "Use precise quantitative language where possible.",
    "Avoid circular definitions.",
    "Structure multi-part questions as separate sub-answers.",
    "Use transition phrases between sections.",
    "Favour depth on the core concept over breadth on tangents.",
    "Restate the question briefly before answering.",
    "Give the shortest correct answer, then expand.",
    "Use the Feynman technique: explain simply enough to teach.",
    "Organise by timeline or history if the topic is evolutionary.",
    "Conclude with a one-sentence 'so what' statement.",
    "Prefer plain English over technical notation where both work.",
    "Use parenthetical definitions for specialised terms.",
    "Ensure every paragraph has a clear main idea.",
    "Give examples from multiple domains.",
    "Highlight what changed in recent research.",
    "Use 'note that' to flag important caveats.",
    "Compare to a concept students already know.",
    "Separate mechanism from motivation.",
    "Point out common pitfalls.",
    "Use 'recall that' to link to previously discussed ideas.",
    "Quantify claims with numbers where available.",
    "Prefer specificity: name algorithms, papers, authors.",
    "Use 'for instance' and 'such as' liberally.",
    "Write for skimmability: bold key terms.",
    "Start paragraphs with the topic sentence.",
    "Avoid passive constructions where possible.",
    "Use signposting phrases like 'importantly' and 'crucially'.",
    "Break steps into atomic actions.",
    "State the output or goal before the method.",
    "Use 'therefore' and 'hence' to make logic explicit.",
    "Give both the formal and informal name of concepts.",
    "Explain from first principles when fundamentals are asked.",
    "Mention scale implications (small vs large data).",
    "Note when a rule of thumb applies.",
    "Use 'in summary' before the closing sentence.",
    "Organise from general to specific.",
    "Use hedging language for uncertain claims.",
    "Provide a brief sanity check or intuition pump.",
    "Flag when two sources disagree.",
    "Recommend a hands-on exercise if appropriate.",
    "Use progressive disclosure: basics first, depth on request.",
    "Adapt detail level to whether the student is exploring or revising.",
]

assert len(REPLY_STYLES) == 100, f"Expected 100 styles, got {len(REPLY_STYLES)}"  # noqa: S101


def select_reply_style(query: str) -> str:
    """Select a deterministic reply style based on the query hash.

    Args:
        query: The user query string.

    Returns:
        A style instruction string chosen from REPLY_STYLES.
    """
    return REPLY_STYLES[hash(query) % len(REPLY_STYLES)]


def strip_style_artifacts(text: str) -> str:
    """Remove hidden LLM style artefacts from user-visible output."""
    if not text:
        return text
    text = re.sub(r"///\s*CITE FIRST\s*///", "", text, flags=re.I)
    text = re.sub(r"\bTHE END\.?\b", "", text, flags=re.I)
    text = re.sub(r"\[END\]", "", text, flags=re.I)
    text = re.sub(r"\[DONE\]", "", text, flags=re.I)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def style_instruction(query: str) -> str:
    """Return a combined style + citation instruction for the given query."""
    style = select_reply_style(query)
    return (
        f"{style} "
        f"Be CONCISE (about 90–220 words). "
        f"Cite sources using bare [S#] markers — at least {_MIN_INLINE_CITATIONS_REQUESTED}, "
        f"at most {_MAX_INLINE_CITATIONS_REQUESTED}. "
        f"Never print style labels or control tokens."
    )
