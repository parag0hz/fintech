# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Not a software project. This directory holds a single deliverable: `idea-brief.html`, a self-contained, Korean-language idea brief for the **2026 금융 AI Challenge** (주최: 금융보안원). It pitches "AI 상담 사각지대" — a post-consultation verification tool that tells consumers what an AI financial counseling session failed to explain (금소법 제19조 compliance). The submission deadline noted in the footer is 2026-09-07.

`idea-brief-v2.html` is currently a byte-identical copy of `idea-brief.html`. Before editing, confirm with the user which file is canonical; do not let them silently diverge.

## Working with the document

There is no build, lint, or test step. Preview by opening the file in a browser (`open idea-brief.html`). There is no git history.

Hard constraints to preserve when editing:

- **No document skeleton.** The file intentionally starts with `<title>` followed by `<style>` and body content — no `<!DOCTYPE>`, `<html>`, `<head>`, or `<body>` tags. This matches the Claude Artifact publishing format (the skeleton is added at publish time). Do not add these tags.
- **Zero JavaScript, zero external resources.** No `<script>` tags, no CDN links, no remote fonts or images. Everything is inline. Interactivity is limited to native HTML (`<details>`/`<summary>` accordions, anchor navigation).
- **Three-state theming.** Every color is a CSS custom property defined in three places: light values on bare `:root`, dark values under `@media (prefers-color-scheme: dark)` guarded as `:root:not([data-theme="light"])`, and the same dark values again under `:root[data-theme="dark"]`. A new color token must be added to all three blocks; never hardcode a color in a rule.
- **Korean typography.** `word-break: keep-all` on body, serif display stack (`AppleMyungjo`/`Nanum Myeongjo`) for `h1` only, sans for body, mono (`--mono`) for metadata labels and rails. Content language is Korean; keep register consistent with the existing text (합니다체 in prose).

## Document architecture

- **Design language:** 관공서 문서 (government-document) aesthetic — cool gray-blue paper (`--paper`), white cards (`--surface`), 인주-red accent (`--seal`) for warnings/competitive flags, blue (`--verify`) for links/verification, amber for caveats. Semantic color use matters: red = risk/rival, blue = verification, amber = weakness.
- **Layout:** one `.wrap` container; each `<section>` uses `.grid` (132px `.rail` margin-label column + `.body-col`), collapsing to a single column under 760px.
- **Section map** (IDs are TOC anchor targets — keep `nav.toc` in sync when adding/removing sections): `#path` (경로), `#problem` (문제), `#product` (제품), `#rival` (경쟁 · 금보원 경고), `#edge` (차별화 5축), `#timing`, `#impact`, `#papers` (선행연구), `#numbers` (현황 수치), `#weak` (약점), `#talk` (논의).
- **Revision tracking:** the masthead `.docmeta` carries a `REV.n` + date (currently REV.2 2026.08.09). Bump it when making substantive content changes.
