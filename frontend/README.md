# Frontend Architecture

Clean, production-oriented frontend separation:

- `chat/`: Core student chat workspace (streaming SSE tokens, natural Markdown, in-chat SVG/force graphs)
- `graph/`: Standalone D3.js force-directed knowledge graph explorer (port 5050/5150)
- `library/`: Institutional catalog browser, ODS holdings table, and upload dropzone
- `landing/`: High-production cinematic landing hero and onboarding introduction
- `quiz/`: 4-option diagnostic multiple choice questions & adaptive learning path visualizer
- `citations/`: Deep-linking badge renderer (#page=N) and verbatim PDF text highlight drawer
- `book-stack/`: link to the hand-written Three.js bookshelf runtime (`ui/chat/library_showcase_3d.js`); `scripts/build_ui.sh` validates both deployed UI copies.
- `shared/`: Shared iconography (`buttons/`), videos, and CSS styling
