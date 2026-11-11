"""Public book catalog for the pilot corpus."""

from __future__ import annotations

BOOKS = [
    # ── DBMS ──
    {
        "dirname": "database_system_concepts_silberschatz",
        "title": "Database System Concepts",
        "authors": "Abraham Silberschatz, Henry F. Korth, S. Sudarshan",
        "publisher": "McGraw Hill",
        "subject": "Database Management Systems",
        "requires": ["Relational Algebra", "B+ Trees", "Disk Storage Architectures"],
        "unlocks": [
            "Transaction Processing (ACID)",
            "Concurrency Control (2PL)",
            "Write-Ahead Logging (WAL)",
            "Query Optimization",
        ],
        "open_access": False,
    },
    {
        "dirname": "database_management_systems_ramakrishnan",
        "title": "Database Management Systems",
        "authors": "Raghu Ramakrishnan, Johannes Gehrke",
        "publisher": "McGraw Hill",
        "subject": "Database Management Systems",
        "requires": ["Functional Dependencies", "Set Theory"],
        "unlocks": [
            "Schema Normalization (3NF, BCNF)",
            "Buffer Pool Management",
            "External Sorting",
            "Hash-based Indexing",
        ],
        "open_access": False,
    },
    # ── DSA ──
    {
        "dirname": "introduction_to_algorithms_clrs",
        "title": "Introduction to Algorithms (CLRS)",
        "authors": "Thomas H. Cormen, Charles E. Leiserson, Ronald L. Rivest, Clifford Stein",
        "publisher": "MIT Press / McGraw Hill",
        "subject": "Data Structures and Algorithms",
        "requires": ["Discrete Math", "Proof Techniques", "Recurrence Relations"],
        "unlocks": [
            "Asymptotic Analysis",
            "Dynamic Programming",
            "Red-Black Trees",
            "Amortized Analysis",
            "Graph Search (BFS, DFS, Dijkstra)",
        ],
        "open_access": False,
    },
    {
        "dirname": "data_structures_algorithm_analysis_weiss",
        "title": "Data Structures and Algorithm Analysis in C++/Java",
        "authors": "Mark Allen Weiss",
        "publisher": "Pearson",
        "subject": "Data Structures and Algorithms",
        "requires": ["Arrays", "Pointers/References", "Recursion"],
        "unlocks": [
            "Priority Queues (Binary Heaps)",
            "Disjoint Set Union-Find",
            "Splay Trees",
            "Hashing (Collision Resolution)",
        ],
        "open_access": False,
    },
    # ── OS ──
    {
        "dirname": "operating_system_concepts_silberschatz",
        "title": "Operating System Concepts (The Dinosaur Book)",
        "authors": "Abraham Silberschatz, Peter B. Galvin, Greg Gagne",
        "publisher": "Wiley",
        "subject": "Operating Systems",
        "requires": ["Assembly/Machine Instructions", "Memory Addressing"],
        "unlocks": [
            "Process Scheduling",
            "Thread Concurrency & Synchronization",
            "Virtual Memory (Paging, TLB)",
            "Deadlock Allocation Graphs",
        ],
        "open_access": False,
    },
    {
        "dirname": "ostep_three_easy_pieces",
        "title": "Operating Systems: Three Easy Pieces (OSTEP)",
        "authors": "Remzi H. Arpaci-Dusseau, Andrea C. Arpaci-Dusseau",
        "publisher": "Arpaci-Dusseau Books (Open Access)",
        "subject": "Operating Systems",
        "requires": ["System Calls", "C Memory Layout (Stack vs Heap)"],
        "unlocks": [
            "Virtualization (CPU & Address Spaces)",
            "Concurrency Primitives",
            "Log-structured File Systems (LFS)",
            "RAID Storage",
        ],
        "open_access": True,
        "ostep_chapters": [
            ("https://pages.cs.wisc.edu/~remzi/OSTEP/dialogue-threeeasy.pdf", "00_Dialogue.pdf"),
            ("https://pages.cs.wisc.edu/~remzi/OSTEP/intro.pdf", "01_Introduction.pdf"),
            ("https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-intro.pdf", "02_CPU_Virtualization.pdf"),
            ("https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-api.pdf", "03_Process_API.pdf"),
            (
                "https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-mechanisms.pdf",
                "04_Limited_Direct_Execution.pdf",
            ),
            ("https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-sched.pdf", "05_CPU_Scheduling.pdf"),
            ("https://pages.cs.wisc.edu/~remzi/OSTEP/vm-intro.pdf", "06_Address_Spaces.pdf"),
            (
                "https://pages.cs.wisc.edu/~remzi/OSTEP/vm-mechanism.pdf",
                "07_Address_Translation.pdf",
            ),
            ("https://pages.cs.wisc.edu/~remzi/OSTEP/vm-paging.pdf", "08_Paging.pdf"),
            ("https://pages.cs.wisc.edu/~remzi/OSTEP/vm-tlbs.pdf", "09_TLBs.pdf"),
            (
                "https://pages.cs.wisc.edu/~remzi/OSTEP/threads-intro.pdf",
                "10_Concurrency_Intro.pdf",
            ),
            ("https://pages.cs.wisc.edu/~remzi/OSTEP/threads-locks.pdf", "11_Locks.pdf"),
            ("https://pages.cs.wisc.edu/~remzi/OSTEP/threads-sema.pdf", "12_Semaphores.pdf"),
            ("https://pages.cs.wisc.edu/~remzi/OSTEP/threads-bugs.pdf", "13_Common_Bugs.pdf"),
            ("https://pages.cs.wisc.edu/~remzi/OSTEP/file-devices.pdf", "14_IO_Devices.pdf"),
            ("https://pages.cs.wisc.edu/~remzi/OSTEP/file-raid.pdf", "15_RAID.pdf"),
            ("https://pages.cs.wisc.edu/~remzi/OSTEP/file-lfs.pdf", "16_Log_Structured_FS.pdf"),
        ],
    },
]

# ═══════════════════════════════════════════════════════════════════════
# Download helpers
