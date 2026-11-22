# Archipelago UI/UX Specification

This document details the UI/UX specification for all frontend surfaces of the Archipelago project, a curriculum-aware Hybrid Graph-Vector RAG Institutional Library Intelligence System.

## 1. Technology Stack
- **Core:** Vanilla HTML5 / CSS3 / JavaScript (NO React/Vue/Angular framework)
- **Graph Visualization:** D3.js v7 for force-directed graphs
- **3D Assets:** Three.js for 3D book showcases
- **Math Rendering:** MathJax/KaTeX for mathematical notations
- **Streaming:** SSE (Server-Sent Events) for real-time chat streaming
- **Source Location:** `host_inference/ui/` (production UI served by hostapp)

## 2. Page Inventory & Status
- `index.html` (53KB) — Main chat UI with SSE streaming, inline SVG graph cards, citation badges [**WORKING**]
- `landing.html` (17KB) — Landing page with KNOWLEDGE OPERATIONS eyebrow, dual CTAs [**WORKING**]
- `library.html` (60KB) — Library catalog browser with book cards [**WORKING**]
- `graph.html` (6KB) — Full D3.js force-directed graph explorer [**WORKING**]
- `login.html` (8.5KB) — Supabase auth login page [**WORKING**]
- `reader.html` (17KB) — PDF/Pearson reader gateway [**WORKING**]
- `performance.html` (10KB) — Performance metrics dashboard [**WORKING**]
- `safety.html` (8KB) — Safety & guardrails info page [**WORKING**]
- **JS Modules:** `auth_bridge.js` (27KB), `chromatic_waves.js` (15KB), `graphify.js` (13KB), `library_showcase_3d.js` (16KB)
- **Styles:** `host_inference/ui/styles/`
- **Assets:** `host_inference/ui/assets/`, `host_inference/ui_assets/` (22 image/video assets including library animation videos)

## 3. Chat UI Specification
- **Streaming:** SSE streaming markdown tokens with real-time rendering.
- **Inline SVG Graph Cards:** Embedded dynamic visualizations supporting 3 modes:
  - Mode A: 3 nodes, 4 edges
  - Mode B: 10 nodes, 16 edges
  - Mode C: 10 nodes, 14 edges
- **Citation Badges:** `[S1]`, `[S2]` notation linking to sources.
- **Deep Links:** Page-level deep links like `#page=N` for Pearson, and `blob/main/` for HuggingFace.
- **Diagnostic MCQ Flow:** Presents 4-option questions inline. *Note: Currently maxes at 4, but specification REQUIRES 10.*
- **Prompts:** Personalized vs Normal choice prompt for learning queries.
- **Book Stack Panel:** Shows relevant resources. [*PARTIAL* — `books_showcase_src.tsx` is currently a 28-byte symlink stub].
- **Query Inspector Panel:** [*NOT YET BUILT* — spec requires collapsible diagnostic console].

## 4. Graph Visualization Spec
- **Graph 1 — Full Backend Graph:** D3.js force-directed in `graph.html`, loaded from `/api/graph`. [**WORKING**]
- **Graph 2 — Chat Mini Graph:** Inline SVG rendered with concept answer, clickable nodes. [**WORKING**]
- **Graph 3 — Personalized Q&A Graph:** Shows mastery states (🟢🟡🎯), generated after diagnostics. [*PARTIAL*]
- **Node Interaction:** Click to navigate or explore concepts.
- **Edge Labels:** `REQUIRES`, `UNLOCKS`, `RELATED`.
- **Color Coding:** Dynamically colored by mastery state and `concept_type`.

## 5. Landing Page Spec
- **Required References:** IEM, UEM, Archipelago, institutional library.
- **Aesthetic:** Dark aesthetic featuring a KNOWLEDGE OPERATIONS eyebrow.
- **CTAs:** Twin action buttons (Chat, Library).
- **Hero Section:** Institutional branding featured prominently.
- **Rule:** NO generic placeholder text.

## 6. Library Page Spec
- **Book Cards:** Includes cover, title, author, and domain.
- **Physical Location Info:** Rack, shelf, and call number.
- **Availability Indicator:** Real-time stock status.
- **Integration:** Pearson reader link / HuggingFace link where applicable.
- **Functionality:** Search and filter tools included.

## 7. 3D Visual Assets — STRICT PRESERVATION
- **Location:** `host_inference/ui_assets/` (22 files).
- **Video Animations:** `final_archi.mp4`, `library_goit.mp4`, `library_hi.mp4`, `library_sucess (1).mp4`, `library_think.mp4`, `library_type.mp4`.
- **Button Icons:** `book_btn.png`, `brain_btn.png`, `cite_btn.png`, `flash_card_btn.png`, `graph_btn.png`, `library_btn.png`, `network_btn.png`, `note_btn.png`, `pdf_btn.png`, `search_btn.png`, `settings_btn.png`.
- **Hero Images:** `intro_archi.jpeg`, `landing_hero_curious.jpg`, `final_archi_poster.jpg`.
- **3D Logic:** Three.js 3D book showcase in `host_inference/ui/library_showcase_3d.js` (16KB).
- **CRITICAL RULE:** NEVER remove, replace, simplify, or break these assets.

## 8. Responsive Design & Accessibility
- **Campus Kiosk Mode:** Full screen, no browser chrome layout.
- **Mobile-Responsive:** Optimized for student phones.
- **Theme:** Dark theme default.
- **Math:** Math formula rendering enabled across text components.

## 9. NOT YET BUILT (from spec)
- **Query Inspector / Glass-Box Diagnostic Console:** Collapsible panel showing intent, vector anchor, graph traversal, OPAC lookup, context tokens.
- **Confidence Slider:** On MCQ answers (🔴 Guessing / 🟡 Somewhat sure / 🟢 Very sure).
- **Fading Mastery Indicators:** 🟠 Fading state UI elements.
- **Transparency Popups:** "Why Am I Seeing This?" overlays.
- **Faculty/Librarian View:** Specialized diagnostic views.
- **Learning Preference Selector:** Toggles for Mathematical / Code / Conceptual.
- **Adaptive Question Budget UI:** Stop early when coverage is sufficient.
- **Gap → Physical Library Mapping Cards.**
- **Librarian Dashboard:** Aggregate demand and metrics view.
