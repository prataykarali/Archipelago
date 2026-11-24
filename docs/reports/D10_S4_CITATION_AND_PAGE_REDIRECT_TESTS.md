# D10-S4 citation and page redirect checks

## Original PDFs inspected in Chrome

The PDFs below came from the pinned `Prataykarali/Library_books` revision `b0561c76a4c5a7a8cb1fe3bd91b389280d504cbd`. Chrome opened the original cached PDF bytes with a `#page=` fragment. This checks the original file and displayed physical page; it does not establish that the deployed Archipelago reader renders the same page.

| Original | SHA-256 | Chrome page | Visible check |
|---|---|---:|---|
| `archipelago-books-cs/ostep_three_easy_pieces/07_Address_Translation.pdf` | `38d81af0ae91743ee39c08c71be620d244b73496536c68c22ccebc2b8a0344a7` | 2 of 15 | Chapter heading and hardware-based address-translation introduction |
| same original | same SHA-256 | 7 of 15 | Base register adds to virtual address; bounds checks legal range |
| `books/papers/Hu2021_LoRA.pdf` | `e9a0d3128767db616085dc0f4e6e455e672e89af823e8ed1282793682787395a` | 1 of 26 | Original LoRA title and low-rank adaptation abstract |
| `books/papers/Lewis2020_RAG.pdf` | `23e3249e9a1e75418d82efecab0ea8c4d033b89c93742f63208d47ce01f21233` | 1 of 19 | Original RAG title and retriever/generator abstract |

The corresponding local browser captures are `/tmp/d10_s4_ostep_address_translation_page2_browser.png`, `/tmp/d10_s4_ostep_address_page7_browser.png`, `/tmp/d10_s4_lora_paper_page1_browser.png`, and `/tmp/d10_s4_rag_paper_page1_browser.png`. They are review evidence on this machine, not repository assets.

## Code and route checks

The OSTEP base-and-bounds diagnostic now has source document `07_Address_Translation.pdf`, physical PDF page 7, and passage `38d81af0ae91:p7:c0` in the candidate with its approved passage index attached. The OSTEP chapter lookup identifies the work as a textbook chapter. The paging page-fault qualification is explicitly marked as a general explanation beyond the cited introductory passage. The deterministic index retains zero-based `pdf_page_index`, one-based `page_number`, explicit printed labels, and text offsets. Synthetic Roman-front-matter tests verify that physical page and printed page remain distinct. Existing citation integrity and D10-S3 redirect tests also pass.

Pearson catalog results continue to use authenticated `/open/<book_id>` book-level handoffs; they do not fabricate a PDF page. The hosted `/api/page-view`, `/api/reader/info`, and `/papers/...` probes returned 401 without an authenticated session, as expected. An authenticated hosted browser and network trace were unavailable in this pass, so the actual application reader redirect and rendered page are **unverified**. Browser status in the worksheet remains blank or blocked, never passed by inference from the source PDF capture.

Source identity, technical answer correctness, passage entailment, and visible reader navigation are independent checks. The Chrome source checks establish only source identity and original PDF page visibility. Human reviewers must still judge each answer's evidence support and test the deployed reader after staging authentication is ready.
