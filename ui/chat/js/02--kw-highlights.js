// Auto-split from ui/chat/index.html — 02--kw-highlights.js
// Feature module 3 of 22.
import { state } from './00-state.js';

        // Curated AI/ML keyword glossary for chat-bubble highlighting.
        // Whole-word, case-insensitive matches only; code/links/headings skipped.
        const _KW_HIGHLIGHTS = [
            'LoRA', 'Low-Rank Adaptation', 'RAG', 'Retrieval-Augmented Generation',
            'BERT', 'GPT', 'Transformer', 'Attention', 'Self-Attention',
            'GraphRAG', 'PEFT', 'QLoRA', 'Adapter', 'Fine-Tuning', 'Fine-Tuning',
            'Embedding', 'Embeddings', 'Vector Database', 'Vector Store',
            'Chunking', 'Retriever', 'Generator', 'Hallucination', 'Tokenization',
            'In-Context Learning', 'Few-Shot', 'Zero-Shot', 'Chain-of-Thought',
            'ReAct', 'Agentic', 'DBMS', 'Buffer Pool', 'B+ Tree', 'Indexing',
            'Paging', 'Virtual Memory', 'TLB', 'PagedAttention', 'vLLM',
            'GNN', 'Graph Neural Network', 'Knowledge Graph', 'Knowledge Representation',
            'OKF', 'Prerequisite', 'Prerequisites', 'Cosine Similarity',
            'Semantic Search', 'Hybrid Search', 'Reranking', 'Reranker',
            'Context Window', 'Temperature', 'Top-K', 'Top-P',
            'Quantization', 'Distillation', 'Pretraining', 'Pre-Training',
        ];

        // Post-render enrichment: wrap curated keywords in <mark class="kw">.
        // Operates on text nodes only, so it never corrupts code/links/markup.
        function _enrichAssistantMarkup(root) {
            if (!root) return;
            // Dedupe + sort by length desc so multi-word phrases win over sub-words.
            const terms = Array.from(new Set(_KW_HIGHLIGHTS.map(t => t.trim())))
                .filter(Boolean)
                .sort((a, b) => b.length - a.length);
            const pattern = new RegExp(
                '\\b(' + terms.map(t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') + ')\\b',
                'gi'
            );

            const SKIP_TAGS = new Set(['A', 'CODE', 'PRE', 'MARK', 'SCRIPT', 'STYLE', 'KBD', 'SAMP']);
            const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
                acceptNode(node) {
                    if (!node.nodeValue || !node.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
                    let p = node.parentNode;
                    while (p && p !== root) {
                        if (SKIP_TAGS.has(p.nodeName)) return NodeFilter.FILTER_REJECT;
                        if (p.classList && (p.classList.contains('katex') || p.classList.contains('katex-mathml'))) return NodeFilter.FILTER_REJECT;
                        // Skip headings — they are already accent-styled.
                        if (/^H[1-6]$/.test(p.nodeName)) return NodeFilter.FILTER_REJECT;
                        p = p.parentNode;
                    }
                    pattern.lastIndex = 0;
                    return pattern.test(node.nodeValue) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
                }
            });

            const targets = [];
            let n;
            while ((n = walker.nextNode())) targets.push(n);
            targets.forEach(node => {
                const text = node.nodeValue;
                let last = 0;
                let m;
                const frag = document.createDocumentFragment();
                pattern.lastIndex = 0;
                while ((m = pattern.exec(text)) !== null) {
                    if (m.index > last) frag.appendChild(document.createTextNode(text.slice(last, m.index)));
                    const mk = document.createElement('mark');
                    mk.className = 'kw';
                    mk.textContent = m[0];
                    frag.appendChild(mk);
                    last = m.index + m[0].length;
                    // Avoid zero-length match spin
                    if (m.index === pattern.lastIndex) pattern.lastIndex++;
                }
                if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
                if (frag.childNodes.length) node.parentNode.replaceChild(frag, node);
            });
        }

        function getResponseCitations(metadata) {
            const candidates = [];
            if (Array.isArray(metadata)) candidates.push(...metadata);
            if (metadata && typeof metadata === 'object') {
                if (Array.isArray(metadata.citations)) candidates.push(...metadata.citations);
                if (metadata.metadata && Array.isArray(metadata.metadata.citations)) candidates.push(...metadata.metadata.citations);
                if (metadata.response && Array.isArray(metadata.response.citations)) candidates.push(...metadata.response.citations);
            }
            const seen = new Set();
            return candidates.filter(citation => {
                if (!citation || typeof citation !== 'object') return false;
                const key = [citation.evidence_id || '', citation.doc_id || citation.document_id || citation.source_id || '', citation.page_number || citation.page || ''].join('|');
                if (seen.has(key)) return false;
                seen.add(key);
                return true;
            });
        }

        const PAPER_TITLE_MAP = {
            'lewis2020_rag.pdf': 'Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks (Lewis et al., 2020)',
            'vaswani2017_attention_is_all_you_need.pdf': 'Attention Is All You Need (Vaswani et al., 2017)',
            'brown2020_gpt3.pdf': 'Language Models are Few-Shot Learners (Brown et al., 2020)',
            'goodfellow2014_gan.pdf': 'Generative Adversarial Nets (Goodfellow et al., 2014)',
            'hu2021_lora.pdf': 'LoRA: Low-Rank Adaptation of Large Language Models (Hu et al., 2021)',
            'dettmers2023_qlora.pdf': 'QLoRA: Efficient Finetuning of Quantized LLMs (Dettmers et al., 2023)',
            'devlin2018_bert.pdf': 'BERT: Pre-training of Deep Bidirectional Transformers (Devlin et al., 2018)',
            'edge2024_graphrag.pdf': 'From Local to Global: A Graph RAG Approach (Edge et al., 2024)',
            'deisenroth_math_for_ml.pdf': 'Mathematics for Machine Learning (Deisenroth et al., 2020)',
            'bahdanau2014_attention.pdf': 'Neural Machine Translation by Jointly Learning to Align and Translate (Bahdanau et al., 2014)',
            'kwon2023_vllm.pdf': 'Efficient Memory Management for LLM Serving with PagedAttention (Kwon et al., 2023)',
            'dao2022_flashattention.pdf': 'FlashAttention: Fast and Memory-Efficient Exact Attention (Dao et al., 2022)',
            'karpukhin2020_dpr.pdf': 'Dense Passage Retrieval for Open-Domain Question Answering (Karpukhin et al., 2020)',
            'hochreiter1997_lstm.pdf': 'Long Short-Term Memory (Hochreiter & Schmidhuber, 1997)',
        };

        function citationTitle(citation, fallback = 'Source') {
            const rawDoc = String(citation.doc_id || citation.document_id || citation.source_id || citation.pdf || '');
            const base = rawDoc.split('/').pop().trim().toLowerCase();
            if (base && PAPER_TITLE_MAP[base]) return PAPER_TITLE_MAP[base];

            const named = citation.doc_title || citation.title || citation.document_title;
            if (named) {
                const namedStr = String(named).trim();
                const namedBase = namedStr.split('/').pop().toLowerCase();
                if (PAPER_TITLE_MAP[namedBase]) return PAPER_TITLE_MAP[namedBase];
                if (!/\.pdf$/i.test(namedStr) && !/_/.test(namedStr)) return namedStr;
            }

            const filename = String(rawDoc || named || fallback).split('/').pop().replace(/\.pdf$/i, '').trim();
            const match = filename.match(/^([A-Za-z]+)(\d{4})[_\-\s]+(.+)$/);
            if (match) {
                const cleanTopic = match[3].replace(/[_-]+/g, ' ').trim();
                return `${cleanTopic} (${match[1]} et al., ${match[2]})`;
            }
            return filename.replace(/[_-]+/g, ' ').trim() || fallback;
        }

        function showPearsonCredentialToast() {
            let t = document.getElementById('archipelago-pearson-toast');
            if (!t) {
                t = document.createElement('div');
                t.id = 'archipelago-pearson-toast';
                t.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);z-index:999999;background:rgba(15,23,42,0.96);color:#f8fafc;padding:12px 18px;border-radius:14px;border:1px solid rgba(245,158,11,0.6);box-shadow:0 12px 36px rgba(0,0,0,0.8);backdrop-filter:blur(16px);font-size:12px;display:flex;align-items:center;gap:10px;pointer-events:auto;transition:all 0.3s ease;';
                document.body.appendChild(t);
            }
            t.innerHTML = `
                <span style="color:#fbbf24;font-weight:700">Pearson eLibrary:</span>
                <span>Sign in with your own institutional account to open licensed books.</span>
            `;
            t.style.opacity = '1';
            t.style.transform = 'translateX(-50%) translateY(0)';
            clearTimeout(window._pearsonToastTimeout);
            window._pearsonToastTimeout = setTimeout(() => {
                t.style.opacity = '0';
                t.style.transform = 'translateX(-50%) translateY(10px)';
            }, 18000);
        }

        function copyPearsonCreds() {
            showPearsonCredentialToast();
        }

        // Dynamically load full Pearson manifest with all slugs and doc_ ids
        fetch('/data/catalogs/pearson_bookshelf.json').then(r => r.json()).then(data => {
            if (data && data.books) {
                for (const b of data.books) {
                    const item = {
                        id: b.id,
                        slug: b.slug || '',
                        type: b.book_type || 'pdf',
                        sub: b.subscription_id || 'debf3e10-c27c-469a-a2aa-8a30c919db91',
                        isbn: b.isbn || '',
                        title: b.title,
                        author: b.author || ''
                    };
                    state.PEARSON_BOOK_CATALOG[b.id] = item;
                    if (b.isbn) state.PEARSON_BOOK_CATALOG[b.isbn] = item;
                    if (b.slug) state.PEARSON_BOOK_CATALOG[b.slug] = item;
                    const cleanT = b.title.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
                    state.PEARSON_BOOK_CATALOG[`doc_${cleanT}`] = item;
                }
            }
        }).catch(() => {});

        const HF_DATASET_BASE = 'https://huggingface.co/datasets/Prataykarali/Library_books/blob/main';

        const HF_CANONICAL_DOCS = {
            'deisenroth_math_for_ml.pdf': 'textbooks/Deisenroth_Math_For_ML.pdf',
            'deisenroth_math_for_ml': 'textbooks/Deisenroth_Math_For_ML.pdf',
            'book_math_for_machine_learning_2020': 'textbooks/Deisenroth_Math_For_ML.pdf',
            'math_for_ml': 'textbooks/Deisenroth_Math_For_ML.pdf',
            'attention_is_all_you_need': 'papers/Vaswani2017_Attention_Is_All_You_Need.pdf',
            'vaswani2017_attention_is_all_you_need.pdf': 'papers/Vaswani2017_Attention_Is_All_You_Need.pdf',
            'paper_attention_is_all_you_need_2017': 'papers/Vaswani2017_Attention_Is_All_You_Need.pdf',
            'bert_paper': 'papers/Devlin2018_BERT.pdf',
            'devlin2018_bert.pdf': 'papers/Devlin2018_BERT.pdf',
            'hu2021_lora.pdf': 'papers/Hu2021_LoRA.pdf',
            'lora_paper': 'papers/Hu2021_LoRA.pdf',
            'dettmers2023_qlora.pdf': 'papers/Dettmers2023_QLoRA.pdf',
            'lewis2020_rag.pdf': 'papers/Lewis2020_RAG.pdf',
            'rag_paper': 'papers/Lewis2020_RAG.pdf',
            'edge2024_graphrag.pdf': 'papers/Edge2024_GraphRAG.pdf',
            'graphrag_ms': 'papers/Edge2024_GraphRAG.pdf',
            'goodfellow2014_gan.pdf': 'papers/Goodfellow2014_GAN.pdf',
            'deep_learning_goodfellow': 'papers/Goodfellow2014_GAN.pdf',
            'paper_goodfellow_2014_gan': 'papers/Goodfellow2014_GAN.pdf',
            'kwon2023_vllm.pdf': 'papers/Kwon2023_vLLM.pdf',
            'brown2020_gpt3.pdf': 'papers/Brown2020_GPT3.pdf',
            'bahdanau2014_attention.pdf': 'papers/Bahdanau2014_Attention.pdf',
            'hochreiter1997_lstm.pdf': 'papers/Hochreiter1997_LSTM.pdf',
        };

        function getPearsonBookEntry(identifier) {
            if (!identifier) return null;
            const raw = String(identifier).trim();
            if (state.PEARSON_BOOK_CATALOG[raw]) return state.PEARSON_BOOK_CATALOG[raw];

            const norm = raw.toLowerCase().replace(/^(doc|pearson|book)_+/, '').replace(/\.pdf$/, '').replace(/[^a-z0-9]/g, '');
            if (!norm) return null;

            for (const [key, book] of Object.entries(state.PEARSON_BOOK_CATALOG)) {
                if (key === norm) return book;
                const bNormTitle = (book.title || '').toLowerCase().replace(/[^a-z0-9]/g, '');
                const bNormSlug = (book.slug || '').toLowerCase().replace(/[^a-z0-9]/g, '');
                const bNormId = (book.id || '').toLowerCase().replace(/[^a-z0-9]/g, '');
                if (norm === bNormTitle || (bNormSlug && norm === bNormSlug) || norm === bNormId) {
                    return book;
                }
                if (norm.length >= 6 && (bNormTitle.includes(norm) || norm.includes(bNormTitle))) {
                    return book;
                }
            }
            return null;
        }

        function citationPageUrl(citation) {
            if (!citation || typeof citation !== 'object') return '';
            let rawPage = Number(citation.page_number ?? citation.page);
            let page = Number.isInteger(rawPage) && rawPage > 0 ? rawPage : null;
            if (!Number.isFinite(page) || page < 1) page = 1;

            const directUrl = citation.reader_url || citation.url || citation.pdf_url || '';

            // The hosted PDF route resolves a filename; /read?doc=papers/... can
            // encode the folder twice and fail in the reader on Vercel.
            if (typeof directUrl === 'string' && directUrl.startsWith('/read?')) {
                const docId = String(citation.doc_id || citation.document_id || '');
                const filename = docId.split('/').pop();
                if (filename && filename.toLowerCase().endsWith('.pdf')) {
                    return `/papers/${encodeURIComponent(filename)}${page ? `#page=${page}` : ''}`;
                }
            }

            if (typeof directUrl === 'string' && (directUrl.startsWith('/open/') || directUrl.startsWith('/read?'))) {
                return directUrl;
            }
            if (typeof directUrl === 'string' && (directUrl.startsWith('/papers/') || directUrl.includes('/papers/'))) {
                const clean = directUrl.split('#')[0];
                return `${clean}${page ? `#page=${page}` : ''}`;
            }

            // 1. Direct Pearson URL already present
            if (typeof directUrl === 'string' && directUrl.includes('pearson.com')) {
                // Reader URLs carry the book in their hash. Appending /page after
                // a query string produces a white Pearson viewer.
                return directUrl;
            }

            // 2. Identify Pearson book from catalog using any candidate ID or title
            const candidates = [
                citation.book_id,
                citation.doc_id,
                citation.document_id,
                citation.source_id,
                citation.title,
                citation.doc_title,
                citation.isbn
            ].filter(Boolean);

            let pEntry = null;
            for (const cand of candidates) {
                pEntry = getPearsonBookEntry(cand);
                if (pEntry) break;
            }

            const isPearson = Boolean(pEntry || citation.is_pearson || citation.subscription_id || citation.source === 'pearson');

            if (isPearson) {
                const subId = (pEntry && pEntry.sub) || citation.subscription_id;
                const bId = (pEntry && pEntry.id) || citation.book_id;
                // Never guess an identifier: without a real book id we would link
                // the reader to an unrelated book, so fall through to the
                // internal page-view reader instead of fabricating a URL.
                if (!subId || !bId) {
                    if (directUrl) return directUrl;
                    return '';
                }
                const bType = (pEntry && pEntry.type) || citation.book_type || 'pdf';
                const viewer = bType === 'reflowable' ? 'index.html' : 'pdfviewer.html';
                const pagePart = page ? `/page/${page}` : '';
                return `https://ebooks.elibrary.in.pearson.com/wr/${viewer}?version=1.0.317.1&subscriptionId=${subId}#book/${bId}${pagePart}`;
            }

            // 3. Saved research URLs are document-level unless a real page was verified.
            if (typeof directUrl === 'string' && directUrl.startsWith('https://')) {
                return directUrl;
            }

            // 4. Hugging Face dataset mapping
            const docId = citation.doc_id || citation.document_id || citation.source_id || citation.pdf || '';
            const raw = String(docId || directUrl || '').trim();
            const cleanDoc = raw.replace(/^https?:\/\/[^\/]+\//, '').replace(/^pdfs\//, '').replace(/^datasets\/[^\/]+\/[^\/]+\/blob\/[^\/]+\//, '');
            const baseName = cleanDoc.split('/').pop().toLowerCase();

            let canonicalDoc = cleanDoc;
            if (HF_CANONICAL_DOCS[baseName]) {
                canonicalDoc = HF_CANONICAL_DOCS[baseName];
            } else if (HF_CANONICAL_DOCS[cleanDoc.toLowerCase()]) {
                canonicalDoc = HF_CANONICAL_DOCS[cleanDoc.toLowerCase()];
            } else if (!canonicalDoc.startsWith('papers/') && !canonicalDoc.startsWith('textbooks/') && !canonicalDoc.startsWith('archipelago-books-cs/')) {
                canonicalDoc = '';
            }

            if (canonicalDoc) {
                return `/read?doc=${encodeURIComponent(canonicalDoc)}${page ? `&page=${page}` : ''}`;
            }

            return '';
        }

        function appendEvidenceRail(messageBody, metadata) {
            if (!messageBody) return;
            const prior = messageBody.querySelector('.evidence-rail');
            if (prior) {
                try { prior.remove(); } catch (_) { /* ignore */ }
            }
            // Keep source navigation in the chat itself.  The inventory is useful
            // context, but it must not be the only way to reach a cited page.
            const rawCitations = getResponseCitations(metadata);
            const deduped = [];
            const seenDocs = new Set();
            for (const citation of rawCitations) {
                const href = citationPageUrl(citation);
                if (!href) continue;
                const docKey = String(
                    citation.doc_id || citation.document_id || citation.book_id || citation.url || href.split('#')[0].split('&page=')[0]
                ).toLowerCase().split('/').pop();
                if (seenDocs.has(docKey)) continue;
                seenDocs.add(docKey);
                deduped.push({ citation, href });
                if (deduped.length >= 5) break;
            }
            messageBody.setAttribute("data-evidence-count", String(deduped.length));
            if (!deduped.length) return;

            const rail = document.createElement('div');
            rail.className = 'evidence-rail mt-4 p-3 rounded-xl border border-purple-500/25 bg-purple-950/25 flex flex-col gap-2';
            const label = document.createElement('div');
            label.className = 'text-[10px] uppercase tracking-wider font-extrabold text-purple-300 flex items-center gap-1.5';
            label.innerHTML = '<i class="fa-solid fa-book-open text-[10px]"></i><span>Resources &amp; Sources</span>';
            rail.appendChild(label);
            const linksWrap = document.createElement('div');
            linksWrap.className = 'flex flex-wrap items-center gap-2';
            rail.appendChild(linksWrap);
            deduped.forEach(({ citation, href }, index) => {
                const rawPage = Number(citation.page_number ?? citation.page);
                const page = Number.isInteger(rawPage) && rawPage > 0 ? rawPage : null;
                const title = citationTitle(citation, `Source ${index + 1}`);
                if (citation.source_type === 'research_paper' || citation.source_type === 'scholarly_source') {
                    const card = document.createElement('details');
                    card.className = 'w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200';
                    const summary = document.createElement('summary');
                    summary.className = 'cursor-pointer font-semibold focus:outline-none focus:ring-2 focus:ring-violet-400';
                    summary.textContent = title;
                    card.appendChild(summary);
                    if (citation.text_span) {
                        const excerpt = document.createElement('p');
                        excerpt.className = 'mt-2 text-xs leading-relaxed text-slate-300';
                        excerpt.textContent = String(citation.text_span);
                        card.appendChild(excerpt);
                    }
                    const sourceLink = document.createElement('a');
                    sourceLink.className = 'mt-2 inline-block text-xs font-semibold text-violet-200 underline focus:outline-none focus:ring-2 focus:ring-violet-400';
                    sourceLink.href = href;
                    sourceLink.target = '_blank';
                    sourceLink.rel = 'noopener noreferrer';
                    sourceLink.textContent = 'Open source ↗';
                    card.appendChild(sourceLink);
                    linksWrap.appendChild(card);
                    return;
                }
                const link = document.createElement('a');
                link.className = 'view-page-link text-[11px] font-semibold';
                link.textContent = page ? `${title} · p. ${page}` : title;
                link.href = href;
                link.dataset.pageUrl = href;
                link.target = '_blank';
                link.rel = 'noopener noreferrer';
                linksWrap.appendChild(link);

            });
            messageBody.appendChild(rail);
        }

export { HF_CANONICAL_DOCS, HF_DATASET_BASE, _KW_HIGHLIGHTS, _enrichAssistantMarkup, appendEvidenceRail, citationPageUrl, citationTitle, copyPearsonCreds, getPearsonBookEntry, getResponseCitations, showPearsonCredentialToast };
