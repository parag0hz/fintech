# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Entry for the **2026 금융 AI Challenge** (주최 금융보안원, 운영 데이콘 — https://daker.ai/public/hackathons/2026-finance-ai-challenge).
Team direction (decided 2026-08-18): **text-to-order 안전 하네스** — a Korean NL→증권 주문 parser running on a local LLM (Qwen family, on-prem constraint), wrapped in a deterministic verification layer ("하네스") that prevents irreversible 매수↔매도 / 이하↔이상 flips, evaluated against frontier-model red-team attack corpora.

Submission (all due **2026-09-07 10:00 KST**): 기획서 PDF (제공 양식) + 기능명세서 PDF (제공 양식) + **실행 가능한 웹서비스 URL** that must stay reachable 9/7 11:00 ~ 9/11 23:59 (결격 사유). No data is provided by the competition — every corpus here is self-generated.

`idea-brief.html` / `idea-brief-v2.html` are the **superseded** earlier idea ("AI 상담 사각지대", 금소법 19조). Keep them for reference; do not extend them.

## Layout

- `smoke/` — Python 3.9+, stdlib only. Experiments, harness, corpora, results. Run from inside `smoke/` (modules import each other). On this Windows box use `py -3` with `$env:PYTHONUTF8="1"` (`python` is a WindowsApps stub).
  - `run.py` — shared library (ORDER_SCHEMA, `call_openrouter` fallback ladder, `normalize`, `score`) + raw benchmark CLI (실험1).
  - `harness.py` — **v2** harness: L1 structural trust split (`history` trusted / `context` untrusted, marker sanitising), L2 prompt + few-shot, L3 deterministic cue engine (`analyze_utterance`, `deterministic_check`, `harness_parse_ex`). `harness_v1.py` is the frozen old version for before/after comparisons.
  - `run_harness.py` — raw vs harness on a corpus (실험2), `--harness v1|v2`, writes aggregate + per-case rows.
  - `run_asr.py` — attacker×defender ASR matrix (실험4), `--harness v1|v2`, writes cells + rows + mech×target heatmap.
  - `generate_attacks.py` (frontier-generated, difficulty 2) / `generate_adaptive.py` (attackers are shown the harness rules, difficulty 3).
  - `test_harness.py` — no-network regression: cue unit tests + corpus checks (perfect model must not be made critical by the harness; flipped model restoration count). Run after any change to `harness.py`.
  - `export_rules.py` — exports `harness_rules.json` + `parity_fixture.json` into `smoke/` and `web/shared/`. **Run after any change to harness patterns**, then run `npm test` in `web/`.
  - `migrate_history.py` — one-off migration of old `context:"직전 대화: …"` cases into the `history` field. Runtime code never infers trust from text.
  - `resummarize.py` — regenerate 실험1 summaries with the current scorer.
  - Corpora: `attacks.jsonl` (47 자체작성), `attacks_frontier9.jsonl` (142, 7 frontier attackers), `attacks_adaptive.jsonl` (difficulty 3). Tags per `TAXONOMY.md` live in `tags_<name>.jsonl` (id → target/mech/mechs/difficulty/gold_suspect).
  - Results: `results_full.json`/`results_q25.json` (실험1), `harness_results*.json` + `harness_rows*.json` (실험2), `asr_<corpus>*.json` + `asr_rows_*.json` (실험4). `legacy/` holds superseded files (do not analyse).
  - Docs: `RESULTS.md` (findings, keep numbers traceable to files), `TAXONOMY.md` (2-axis attack taxonomy), `PAPERS.md` (verified references).
- `web/` — Node 22 / TypeScript / Express, no frontend framework, no CDN. The competition MVP: 파서 데모 (raw vs 하네스), 공격 코퍼스 브라우저, 결과 대시보드. `src/harness.ts` is a port of `harness.py` driven by `shared/harness_rules.json`; `npm test` checks 100% parity against `shared/parity_fixture.json`. `npm run sync-data` copies smoke JSON into `web/data/` for deployment.

## Conventions

- Critical error = committed order (`abstain=false`) with `side` or `condition` ≠ gold (`run_harness.hscore`). 실험1's `run.score` is the older non-gated definition — say which one you use.
- Never count failed API calls as attacks; record them (`errors`) and exclude.
- Any harness rule change → `py -3 test_harness.py` → `py -3 export_rules.py` → `cd web && npm test`.
- Secrets: `smoke/.env` and `web/.env` hold `OPENROUTER_API_KEY`; both are git-ignored. Never print keys.
- Korean UI/text in 합니다체. Model slugs are OpenRouter slugs; production target is on-prem Qwen (OpenRouter is only the test proxy — full precision, so numbers are an optimistic bound for 4-bit local).
