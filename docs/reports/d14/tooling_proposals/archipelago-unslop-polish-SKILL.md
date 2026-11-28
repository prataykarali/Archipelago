---
name: archipelago-unslop-polish
description: >
  Polish-mode UI craft audit and refinement for Archipelago's /chat 3D workspace
  and Concept Inspector (D14.6), adapted from unslop (CC BY 4.0, Damir Sokolovsky /
  @heydamir). Strips generic AI-slop chrome while preserving Archipelago's restored
  3D knowledge-graph identity, accessibility, and host_inference/ui <-> ui/chat mirror.
license: CC-BY-4.0
metadata:
  adapted_from: https://github.com/heydamir/unslop
  author_upstream: Damir Sokolovsky (@heydamir)
---

# Archipelago Unslop — Polish Mode (D14.6)

Adapted from **unslop** by Damir Sokolovsky ([@heydamir](https://x.com/heydamir), [github.com/heydamir/unslop](https://github.com/heydamir/unslop)), licensed under **CC BY 4.0**. Keep this attribution in any copy or adaptation.

## Operating Mode: Light Slop / Polish Mode ONLY

Do **not** redesign Archipelago from scratch or discard its restored identity. Keep the existing page structure, features, and 3D knowledge-graph / Concept Inspector workflow on `sigir/d14-recovery`.

### Fixed Archipelago Direction
- **Product:** Academic literature & concept-graph exploration workspace for students and researchers (ACM SIGIR 2027 Demo).
- **Character:** `scholarly, precise, calm`.
- **World:** Cartographic atlas and library reading desk — dark neutral slate/graphite surfaces so citations, equations, and the 3D knowledge graph carry the visual focus.
- **One Bright Moment:** The interactive 3D Knowledge Graph / Concept Map & Chromatic Canvas. Everything around it (sidebar, buttons, badges, Inspector headers) stays quiet.
- **Signature Detail:** Clean concept-node hairlines and tabular citation/graph metadata.

## Audit Targets (Known Tells in `host_inference/ui/index.html`)

1. **Surfaces & Color:** Remove blurred multi-hue background blobs (`bg-accentPurple`/`bg-accentPink`/`bg-accentCyan` `blur-[120px] animate-blob`), hue-to-hue button gradients (`from-accentPink/25 to-accentPurple/25`, `from-accentPurple to-indigo-600`), and neon colored shadows (`shadow-[0_0_24px_rgba(...)]`). Use neutral surface steps + 6–10% hairline borders + one restrained accent with `>=4.5:1` contrast.
2. **Type & Hierarchy:** Replace `text-[9px] font-extrabold uppercase` glowing pills with legible `>=11px` sentence-case text, weights `400–600`, and `tabular-nums` for counts/latencies.
3. **Spacing & Alignment:** Snap one-off margins/paddings to the 4px grid; align sidebar icons and labels into consistent columns.
4. **Copy & Honesty:** Remove hype adjectives, exclamation marks, and misleading status copy (e.g., never show "Pending completion" after a stream finishes, and never render empty/broken `href` source links).
5. **Motion:** Replace `transition-all` with explicit `transition-colors` or `transition-[transform,opacity]`; keep `animate-pulse` strictly for genuinely live indicators (never decorative loops).
6. **Accessibility (`AGENTS.md` Law 4):** Visible keyboard focus rings on every interactive control, clear ARIA labels on Send/Stop/Inspector toggles, and verified contrast.

## Mandatory D14 Guardrails

- **Mirror Invariant:** Every edit to `host_inference/ui/<path>` MUST be mirrored identically to `ui/chat/<path>`.
- **No Paid Image Gen:** Never invoke external image-generation MCPs for app chrome.
- **Verify Visually:** Capture before/after screenshots via Playwright on local/staging `/chat` (never UEM production `archipelago-blond.vercel.app`) and confirm zero JS console errors.
