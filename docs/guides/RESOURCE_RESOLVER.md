# Archipelago Resource Resolver & Deep-Linking Guide

This document describes the design, architecture, and operational workflows for resource deep-linking, authenticated access, and reconciliation across the 46-book institutional library in Archipelago.

---

## 1. Architecture Overview

Archipelago provides access to academic resources across multiple distinct modalities:
- **Pearson eLibrary Textbooks (40 titles)**: Proprietary, requiring institutional SSO/session cookies or portal authentication.
- **Hugging Face Textbooks & Papers**: Hosted in dataset repository `Prataykarali/Library_books`.
- **Local Open-Access Textbooks & PDFs**: Stored on-premise under `pdfs/`.
- **Reference-Only Metadata Textbooks**: Holding metadata and citation graph lineage.

```
                  ┌───────────────────────────────┐
                  │ Library UI / 3D Shelf / Chat  │
                  └───────────────┬───────────────┘
                                  │
                          /resolve/<book_id>
                                  │
                                  ▼
                   ┌──────────────────────────────┐
                   │  LinkResolver Cascade Router │
                   └──────────────┬───────────────┘
          ┌───────────────────────┼───────────────────────┐
          ▼                       ▼                       ▼
┌───────────────────┐   ┌───────────────────┐   ┌───────────────────┐
│ Resource Registry │   │ HuggingFace       │   │ Pearson eLibrary  │
│ (46 Books/Papers) │   │ Hub Resolver      │   │ Resolver Engine   │
└───────────────────┘   └─────────┬─────────┘   └─────────┬─────────┘
                                  │                       │
                                  ▼                       ▼
                        blob_url / resolve_url   pdfviewer.html / SSO
```

---

## 2. Root Cause Analysis: Black PDF Screen in Hugging Face Spaces

### The Problem
When Archipelago is embedded in an external iframe (such as inside a Hugging Face Space at `hf.space/spaces/...`), clicking an external resource link previously resulted in a **black screen** or blocked navigation.

### The Mechanism
1. The backend issued a bare HTTP `302 Found` redirect to the target URL.
2. The browser attempted to execute this redirect inside the embedded `<iframe>`.
3. Destination sites (Pearson eLibrary, Hugging Face blob pages) set `X-Frame-Options: SAMEORIGIN` or `Content-Security-Policy: frame-ancestors 'self'`.
4. The browser blocked loading the destination frame cross-origin, rendering a blank/black canvas.

### The Fix
The `/resolve/<book_id>` route in `chat_server.py` now responds with an iframe-aware HTML redirect shell (`_build_redirect_shell`):
```html
<script>
  if (window.top !== window.self) {
    // Escapes iframe nesting into a new browser tab
    window.open(target_url, "_blank", "noopener,noreferrer");
  } else {
    // Native top-level navigation
    window.location.href = target_url;
  }
</script>
<a href="..." target="_blank" rel="noopener noreferrer">Open Manually</a>
```

---

## 3. The 46-Resource Catalog Reconciliation

Archipelago tracks a reconciled corpus of exactly **46 unique resources**:
- **40 Pearson eLibrary Titles**: Institutional textbooks in Computer Science, Systems, AI, and Electronics.
- **2 Hugging Face Hosted Resources**:
  - `papers/Vaswani2017_Attention_Is_All_You_Need.pdf`
  - `textbooks/Deisenroth_Math_For_ML.pdf`
- **2 Local PDFs**:
  - `ostep_three_easy_pieces` (*Operating Systems: Three Easy Pieces*, Arpaci-Dusseau)
  - `corpus_book_artificial_intelligence_a_new_synthesis_1998` (*AI: A New Synthesis*, Nilsson)
- **2 Reference Metadata Resources**:
  - `book_deep_learning_goodfellow_2016` (*Deep Learning*, Goodfellow et al.)
  - `book_speech_and_language_processing_jurafsky` (*Speech & Language Processing*, Jurafsky & Martin)

### Reconciliation Summary
```
RESOURCE SYNC
=============
Total:        46
Hugging Face:  2
Pearson:      40
Local PDF:     2
Metadata-only: 2

Resolved:     45
Missing:       1 (Nilsson PDF awaiting local archive ingest)
Auth Required: 0
Stale:         0
Duplicates:    0

Completed: 97.83%
```

---

## 4. Pearson Authentication & Session Bootstrap

Pearson eLibrary requires authenticated sessions for direct deep-linking to reader pages (`/wr/pdfviewer.html?subscriptionId=...#book/...`).

### First-Time Setup (CLI Bootstrap)
To initialize the Playwright authentication state:
```bash
python -m archipelago.resolver.pearson_login
```
This launches a visible browser window, allows the administrator to log into Pearson eLibrary, and captures the storage state (cookies, local storage, auth tokens) to:
```
data/catalogs/pearson_auth_state.json
```
*(This file is gitignored and excluded from version control for security).*

To verify an existing session without re-opening a browser:
```bash
python -m archipelago.resolver.pearson_login --verify-only
```

### Normal Operation & Fallback
When a user clicks "Open" on a Pearson textbook:
1. If an active session state exists, the resolver opens the reader URL directly in a new tab.
2. If unauthenticated, the user is presented with the institutional access prompt and directed through SSO login.

---

## 5. Hugging Face Canonical URL Dual-Mode Strategy

For any Hugging Face resource, the resolver generates two canonical URLs:
1. **Browser-Readable Page (`blob_url`)**:
   `https://huggingface.co/datasets/Prataykarali/Library_books/blob/main/textbooks/Deisenroth_Math_For_ML.pdf`
   *Used for user-facing interactive viewing in the browser.*
2. **Direct Download URL (`resolve_url`)**:
   `https://huggingface.co/datasets/Prataykarali/Library_books/resolve/main/textbooks/Deisenroth_Math_For_ML.pdf`
   *Used for headless backend PDF extraction, chunking, and embedding pipelines.*

### Repository File Verification
`verify_hf_repo_file` checks file existence against the repository tree (cached in-memory for 1 hour). If a file does not exist in the repository, the resolver flags `working: False` and `status: "missing"`, preventing broken links.

---

## 6. CLI Administration Tools

### 1. Batch Resource Sync
Audit all 46 resources, detect duplicates, and output reconciliation metrics:
```bash
python -m archipelago.resolver.sync
```
For machine-readable JSON output:
```bash
python -m archipelago.resolver.sync --json
```

### 2. Interactive Pearson Login
Bootstrap authentication context for headless resolvers:
```bash
python -m archipelago.resolver.pearson_login
```

### 3. Concurrent Link Checker
Check all 46 links concurrently using ThreadPoolExecutor:
```bash
python -m archipelago.resolver.check_links
```

---

## 7. Security Best Practices

1. **No Credentials in Frontend APIs**: Institutional passwords have been completely purged from the `/api/library/data` JSON endpoint and frontend templates.
2. **Environment Variable Loading**: Private Hugging Face access tokens are loaded strictly via `HF_TOKEN` in the root `.env` file (never committed to git).
3. **Session Cache Protection**: All `pearson_auth_state.json` and session cache artifacts are added to `.gitignore`.
