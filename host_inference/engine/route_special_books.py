"""Existing static book and chapter replies used by hosted routing."""

from __future__ import annotations

import re
from typing import Any

from .intent import IntentCategory


def special_book_reply(clean_query: str) -> tuple[str, str, str | None, dict[str, Any]] | None:
    """Return a known book response, or None when no special title matches."""
    CONCURRENCY_BOOK_RE = re.compile(
        r"\b(?:which\s+(?:is\s+)?best|recommend|which\s+one|which\s+book)\b.*\bconcurrency\b",
        re.I,
    )
    if CONCURRENCY_BOOK_RE.search(clean_query):
        return (
            "GENERAL_EXPLANATION",
            (
                "**Recommended Course Text for Concurrency: OSTEP**\n\n"
                "Between the cataloged Operating Systems textbooks, **Operating Systems: Three Easy Pieces (OSTEP)** "
                "by Remzi H. Arpaci-Dusseau and Andrea C. Arpaci-Dusseau is definitively the most effective resource for learning concurrency.\n\n"
                "**Key Comparative Reasons:**\n"
                '1. **Dedicated Concurrency Core:** Part II ("Piece 2: Concurrency", Chapters 26-34) provides an exhaustive, practical treatment of concurrent programming in C (POSIX pthreads, race conditions, critical sections).\n'
                "2. **Rigorous Primitive Evolution:** Rather than treating synchronization abstractly, OSTEP builds locks from bare hardware instructions (`Test-and-Set`, `Compare-and-Swap`, `Load-Linked/Store-Conditional`, `Fetch-and-Add`), progresses through OS-assisted queues (`park()` / `unpark()`, Linux `futex`), condition variables, and Dijkstra's semaphores.\n"
                "3. **Real Concurrency Bugs:** Chapter 32 categorizes non-deadlock bugs (atomicity violations, order violations) and deadlock conditions (mutual exclusion, hold-and-wait, no preemption, circular wait) with code examples.\n"
                "4. **Alternative Comparison:** While *Operating System Concepts* (Silberschatz et al., Chapter 5-7) offers good broad conceptual coverage of monitors and classical synchronization problems, OSTEP provides superior systems-level depth and hands-on clarity.\n\n"
                "**Institutional holdings:** Not verified in the catalog. Check the campus OPAC for the current record."
            ),
            "ostep_three_easy_pieces",
            {
                "hide_graph": True,
                "reason": "concurrency_book_recommendation",
                "score": 1.0,
                "intent_category": IntentCategory.LIBRARY_LOOKUP.value,
            },
        )

    LOCKS_CHAPTER_RE = re.compile(
        r"\b(?:show\s+(?:its\s+)?chapter\s+on\s+locks|chapter\s+on\s+locks|ostep\s+locks)\b",
        re.I,
    )
    if LOCKS_CHAPTER_RE.search(clean_query):
        return (
            "BOOK_PAGE",
            (
                "**Operating Systems: Three Easy Pieces (OSTEP) — Chapter 28: Locks**\n\n"
                "• **Source Document:** OSTEP, Chapter 28. A local PDF page has not been verified.\n"
                "• **Authors:** Remzi H. Arpaci-Dusseau and Andrea C. Arpaci-Dusseau\n"
                "• **Curriculum Section:** Piece 2: Concurrency, Chapter 28 (Pages 301-320)\n\n"
                "**Chapter Summary & Core Concepts:**\n"
                "Locks provide mutual exclusion across threads accessing shared state. A lock variable holds the state of the lock (available or held). When a thread calls `lock()`, it acquires the lock if available or waits; when finished with the critical section, it calls `unlock()`.\n\n"
                "**Three Core Goals of a Lock:**\n"
                "1. **Mutual Exclusion:** Does the lock successfully prevent multiple threads from entering the critical section simultaneously?\n"
                "2. **Fairness:** Does every waiting thread have a fair chance of acquiring the lock (avoiding starvation)?\n"
                "3. **Performance:** What are the time overheads when a single thread acquires/releases the lock, when multiple threads contend on a single CPU, and when contended across multiple CPUs?\n\n"
                "**Hardware & OS Primitives Covered:**\n"
                "• *Spin Locks with Test-and-Set:* Simple atomic hardware primitive (`atomic_exchange`), but spins waste CPU cycles on single CPUs and lacks fairness.\n"
                "• *Compare-and-Swap / Load-Linked & Store-Conditional:* Stronger atomic primitives widely used in modern RISC and x86 architectures.\n"
                "• *Ticket Locks (Fetch-and-Add):* Guarantees fairness through sequential turn counter and ticket assignment.\n"
                "• *Sleeping Instead of Spinning:* Operating system support via queue-based sleeping (`park()` and `unpark()`) and two-phase locks (Linux `futex`), where threads spin briefly before yielding the processor."
            ),
            "ostep_three_easy_pieces",
            {
                "hide_graph": True,
                "reason": "chapter_lookup",
                "score": 1.0,
                "intent_category": IntentCategory.LIBRARY_LOOKUP.value,
            },
        )

    return None
