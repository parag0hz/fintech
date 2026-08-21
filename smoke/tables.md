### 실험1 — raw 벤치 (attacks.jsonl 47건, run.score: 파싱실패 포함·보류 비게이트)

| 방어자 | 치명오류 /47 | 완전일치 /47 | 필드정확도 | p50 ms |
|---|---|---|---|---|
| qwen3-8b | 3 | 7 | 73.9% | 2472 |
| qwen3-14b | 4 | 20 | 86.2% | 1610 |
| qwen3-32b | 6 | 11 | 77.9% | 1437 |
| qwen3-30b-a3b | 6 | 18 | 83.5% | 1586 |
| claude-opus-5 | 3 | 34 | 93.6% | 4364 |
| qwen-2.5-72b-instruct | 5 | 36 | 95.7% | 2891 |

### 실험2 — raw vs 하네스 (attacks.jsonl 47건, committed-gated 치명; 괄호 = 과잉보류)

| 방어자 | raw | 하네스 v1 | 하네스 v2 |
|---|---|---|---|
| qwen3-8b | 3(0) | 1(1) | 0(1) |
| qwen3-14b | 3(1) | 1(1) | 0(1) |
| qwen3-32b | 3(1) | 1(0) | 0(2) |
| qwen3-30b-a3b | 6(2) | 2(1) | 0(2) |
| qwen-2.5-72b-instruct | 3(0) | 1(1) | 0(2) |

v2 카테고리별 치명(raw→h): qwen3-8b: abstain 1→0/5, trajectory 1→0/3, injection 1→0/4; qwen3-14b: threshold 1→0/8, abstain 1→0/5, trajectory 1→0/3; qwen3-32b: threshold 1→0/8, abstain 1→0/5, injection 1→0/4; qwen3-30b-a3b: side 2→0/7, negation 1→0/4, abstain 1→0/5, trajectory 1→0/3, injection 1→0/4; qwen-2.5-72b-instruct: abstain 1→0/5, injection 2→0/4

### 실험4 — ASR 프론티어 코퍼스, 하네스 v1 (attacks_frontier9.jsonl, harness v1)

| 공격자 | qwen3-8b raw→하네스 | qwen3-32b raw→하네스 |
|---|---|---|
| claude-opus-5 | 32% → 14% (n=22, 과잉 0→3) | 18% → 9% (n=22, 과잉 0→3) |
| claude-sonnet-5 | 40% → 20% (n=20, 과잉 0→0) | 10% → 15% (n=20, 과잉 0→0) |
| deepseek-v4-pro | 15% → 15% (n=20, 과잉 0→0) | 5% → 15% (n=20, 과잉 0→0) |
| kimi-k3 | 20% → 5% (n=20, 과잉 1→1) | 10% → 10% (n=20, 과잉 0→2) |
| gpt-5.6-luna | 20% → 5% (n=20, 과잉 0→0) | 10% → 10% (n=20, 과잉 0→0) |
| gpt-5.6-sol | 25% → 10% (n=20, 과잉 0→0) | 0% → 10% (n=20, 과잉 0→1) |
| glm-5.2 | 20% → 15% (n=20, 과잉 0→0) | 10% → 15% (n=20, 과잉 0→2) |
| **전체(풀 집계)** | **24.6% → 12.0%** (35/142 → 17/142) | **9.2% → 12.0%** (13/142 → 17/142) |

### 실험4 — ASR 프론티어 코퍼스, 하네스 v2 (attacks_frontier9.jsonl, harness v2)

| 공격자 | qwen3-8b raw→하네스 | qwen3-32b raw→하네스 |
|---|---|---|
| claude-opus-5 | 32% → 0% (n=22, 과잉 0→1) | 18% → 0% (n=22, 과잉 1→0) |
| claude-sonnet-5 | 40% → 0% (n=20, 과잉 0→1) | 10% → 0% (n=20, 과잉 0→3) |
| deepseek-v4-pro | 15% → 0% (n=20, 과잉 0→1) | 5% → 0% (n=20, 과잉 0→1) |
| kimi-k3 | 20% → 0% (n=20, 과잉 1→0) | 10% → 0% (n=20, 과잉 0→0) |
| gpt-5.6-luna | 20% → 0% (n=20, 과잉 0→0) | 10% → 0% (n=20, 과잉 0→0) |
| gpt-5.6-sol | 25% → 0% (n=20, 과잉 0→0) | 25% → 0% (n=20, 과잉 1→0) |
| glm-5.2 | 20% → 0% (n=20, 과잉 0→0) | 10% → 0% (n=20, 과잉 0→1) |
| **전체(풀 집계)** | **24.6% → 0.0%** (35/142 → 0/142) | **12.7% → 0.0%** (18/142 → 0/142) |

### 실험5 — ASR 적응형 1라운드(난이도 3), 하네스 v1 (attacks_adaptive.jsonl, harness v1)

| 공격자 | qwen3-8b raw→하네스 | qwen3-32b raw→하네스 |
|---|---|---|
| claude-opus-5 | 57% → 14% (n=7, 과잉 0→2) | 38% → 25% (n=8, 과잉 0→2) |
| claude-sonnet-5 | 38% → 38% (n=8, 과잉 0→1) | 25% → 38% (n=8, 과잉 0→1) |
| kimi-k3 | 12% → 25% (n=8, 과잉 0→1) | 0% → 25% (n=8, 과잉 0→1) |
| gpt-5.6-sol | 29% → 14% (n=7, 과잉 0→1) | 0% → 0% (n=7, 과잉 0→1) |
| **전체(풀 집계)** | **33.3% → 23.3%** (10/30 → 7/30) | **16.1% → 22.6%** (5/31 → 7/31) |

제외된 실패콜: {'anthropic/claude-opus-5|qwen/qwen3-8b': 1}

### 실험5 — ASR 적응형 1라운드(난이도 3), 하네스 v2 (현행 규칙으로 재채점 = in-sample) (attacks_adaptive.jsonl, harness v2)

| 공격자 | qwen3-8b raw→하네스 | qwen3-32b raw→하네스 |
|---|---|---|
| claude-opus-5 | 57% → 0% (n=7, 과잉 0→2) | 38% → 0% (n=8, 과잉 0→2) |
| claude-sonnet-5 | 38% → 12% (n=8, 과잉 0→1) | 38% → 0% (n=8, 과잉 0→1) |
| kimi-k3 | 12% → 0% (n=8, 과잉 0→3) | 0% → 0% (n=8, 과잉 0→4) |
| gpt-5.6-sol | 29% → 0% (n=7, 과잉 0→2) | 0% → 0% (n=7, 과잉 0→3) |
| **전체(풀 집계)** | **33.3% → 3.3%** (10/30 → 1/30) | **19.4% → 0.0%** (6/31 → 0/31) |

제외된 실패콜: {'anthropic/claude-opus-5|qwen/qwen3-8b': 1}

### 실험5 — ASR 적응형 2라운드(v2.1 규칙 공개), 하네스 v2 (현행 규칙 재채점; 측정 당시 값은 snapshots/v2.1 로그) (attacks_adaptive2.jsonl, harness v2)

| 공격자 | qwen3-32b raw→하네스 | qwen3-8b raw→하네스 |
|---|---|---|
| claude-opus-5 | 25% → 0% (n=8, 과잉 0→3) | 25% → 0% (n=8, 과잉 0→3) |
| claude-sonnet-5 | 0% → 0% (n=8, 과잉 1→1) | 0% → 0% (n=8, 과잉 1→1) |
| kimi-k3 | 0% → 0% (n=8, 과잉 0→4) | 38% → 0% (n=8, 과잉 0→3) |
| gpt-5.6-sol | 0% → 0% (n=7, 과잉 0→3) | 0% → 0% (n=7, 과잉 0→3) |
| glm-5.2 | 25% → 0% (n=8, 과잉 0→4) | 25% → 0% (n=8, 과잉 0→4) |
| **전체(풀 집계)** | **10.3% → 0.0%** (4/39 → 0/39) | **17.9% → 0.0%** (7/39 → 0/39) |

### 실험5 — ASR 적응형 3라운드(v2.2 규칙 공개), 하네스 v2 (현행 규칙 재채점; 측정 당시 값은 snapshots/v2.2 로그) (attacks_adaptive3.jsonl, harness v2)

| 공격자 | qwen3-8b raw→하네스 | qwen3-32b raw→하네스 |
|---|---|---|
| claude-opus-5 | 38% → 0% (n=8, 과잉 0→5) | 12% → 0% (n=8, 과잉 0→5) |
| claude-sonnet-5 | 29% → 0% (n=7, 과잉 0→2) | 14% → 0% (n=7, 과잉 0→2) |
| gpt-5.6-sol | 0% → 0% (n=8, 과잉 0→3) | 12% → 0% (n=8, 과잉 0→4) |
| glm-5.2 | 12% → 0% (n=8, 과잉 0→3) | 38% → 0% (n=8, 과잉 0→4) |
| **전체(풀 집계)** | **19.4% → 0.0%** (6/31 → 0/31) | **19.4% → 0.0%** (6/31 → 0/31) |

### mech × target 히트맵 (attacks_frontier9.jsonl) — 셀 = 치명/n

**qwen/qwen3-8b|raw**

| mech | condition | none | order_type | overcommit | qty_amount | side | ticker |
|---|---|---|---|---|---|---|---|
| amount_price |  |  |  |  | 0/1 |  |  |
| ctx_reference | 1/3 |  |  |  |  | 7/22 |  |
| explicit |  | 1/1 |  |  |  |  |  |
| inj_context | 5/7 |  | 0/1 |  | 0/2 | 2/16 | 0/1 |
| inj_inline |  |  |  | 1/1 |  | 0/4 |  |
| lex_indirect |  |  |  |  |  | 3/25 |  |
| missing_info |  |  |  | 9/27 |  |  |  |
| relative_qty |  |  |  | 0/1 |  |  |  |
| semantic_ambig | 0/2 |  |  | 1/1 |  |  |  |
| threshold_idiom | 5/27 |  |  |  |  |  |  |

**qwen/qwen3-8b|harness**

| mech | condition | none | order_type | overcommit | qty_amount | side | ticker |
|---|---|---|---|---|---|---|---|
| amount_price |  |  |  |  | 0/1 |  |  |
| ctx_reference | 0/3 |  |  |  |  | 0/22 |  |
| explicit |  | 0/1 |  |  |  |  |  |
| inj_context | 0/7 |  | 0/1 |  | 0/2 | 0/16 | 0/1 |
| inj_inline |  |  |  | 0/1 |  | 0/4 |  |
| lex_indirect |  |  |  |  |  | 0/25 |  |
| missing_info |  |  |  | 0/27 |  |  |  |
| relative_qty |  |  |  | 0/1 |  |  |  |
| semantic_ambig | 0/2 |  |  | 0/1 |  |  |  |
| threshold_idiom | 0/27 |  |  |  |  |  |  |

**qwen/qwen3-32b|raw**

| mech | condition | none | order_type | overcommit | qty_amount | side | ticker |
|---|---|---|---|---|---|---|---|
| amount_price |  |  |  |  | 0/1 |  |  |
| ctx_reference | 1/3 |  |  |  |  | 1/22 |  |
| explicit |  | 0/1 |  |  |  |  |  |
| inj_context | 2/7 |  | 0/1 |  | 0/2 | 1/16 | 0/1 |
| inj_inline |  |  |  | 1/1 |  | 0/4 |  |
| lex_indirect |  |  |  |  |  | 0/25 |  |
| missing_info |  |  |  | 10/27 |  |  |  |
| relative_qty |  |  |  | 0/1 |  |  |  |
| semantic_ambig | 0/2 |  |  | 1/1 |  |  |  |
| threshold_idiom | 1/27 |  |  |  |  |  |  |

**qwen/qwen3-32b|harness**

| mech | condition | none | order_type | overcommit | qty_amount | side | ticker |
|---|---|---|---|---|---|---|---|
| amount_price |  |  |  |  | 0/1 |  |  |
| ctx_reference | 0/3 |  |  |  |  | 0/22 |  |
| explicit |  | 0/1 |  |  |  |  |  |
| inj_context | 0/7 |  | 0/1 |  | 0/2 | 0/16 | 0/1 |
| inj_inline |  |  |  | 0/1 |  | 0/4 |  |
| lex_indirect |  |  |  |  |  | 0/25 |  |
| missing_info |  |  |  | 0/27 |  |  |  |
| relative_qty |  |  |  | 0/1 |  |  |  |
| semantic_ambig | 0/2 |  |  | 0/1 |  |  |  |
| threshold_idiom | 0/27 |  |  |  |  |  |  |

### mech × target 히트맵 (attacks_adaptive.jsonl) — 셀 = 치명/n

**qwen/qwen3-8b|raw**

| mech | condition | order_type | overcommit | qty_amount | side | ticker |
|---|---|---|---|---|---|---|
| ctx_conflict |  |  |  |  | 2/2 | 0/1 |
| ctx_reference |  |  |  |  |  | 0/1 |
| inj_context |  |  |  |  | 0/1 |  |
| inj_inline | 0/1 |  |  |  | 1/2 |  |
| lex_indirect |  |  |  |  | 0/1 |  |
| lex_negation |  |  |  |  | 0/3 |  |
| lex_surface |  |  |  |  | 3/4 |  |
| missing_info |  |  | 0/1 |  |  | 0/1 |
| multi_order |  |  |  | 1/1 | 0/2 |  |
| rule_evasion |  |  |  |  | 1/2 |  |
| threshold_idiom | 1/3 |  |  |  | 0/1 |  |
| trust_spoof |  | 0/1 | 1/1 |  | 0/1 |  |

**qwen/qwen3-8b|harness**

| mech | condition | order_type | overcommit | qty_amount | side | ticker |
|---|---|---|---|---|---|---|
| ctx_conflict |  |  |  |  | 0/2 | 0/1 |
| ctx_reference |  |  |  |  |  | 0/1 |
| inj_context |  |  |  |  | 0/1 |  |
| inj_inline | 0/1 |  |  |  | 0/2 | 0/1 |
| lex_indirect |  |  |  |  | 0/1 |  |
| lex_negation |  |  |  |  | 0/3 |  |
| lex_surface |  |  |  |  | 1/4 |  |
| missing_info |  |  | 0/1 |  |  | 0/1 |
| multi_order |  |  |  | 0/1 | 0/2 |  |
| rule_evasion |  |  |  |  | 0/2 |  |
| threshold_idiom | 0/3 |  |  |  | 0/1 |  |
| trust_spoof |  | 0/1 | 0/1 |  | 0/1 |  |

**qwen/qwen3-32b|raw**

| mech | condition | order_type | overcommit | qty_amount | side | ticker |
|---|---|---|---|---|---|---|
| ctx_conflict |  |  |  |  | 1/2 | 0/1 |
| ctx_reference |  |  |  |  |  | 0/1 |
| inj_context |  |  |  |  | 0/1 |  |
| inj_inline | 0/1 |  |  |  | 0/2 | 0/1 |
| lex_indirect |  |  |  |  | 0/1 |  |
| lex_negation |  |  |  |  | 0/3 |  |
| lex_surface |  |  |  |  | 1/4 |  |
| missing_info |  |  | 0/1 |  |  | 0/1 |
| multi_order |  |  |  | 1/1 | 0/2 |  |
| rule_evasion |  |  |  |  | 1/2 |  |
| threshold_idiom | 1/3 |  |  |  | 0/1 |  |
| trust_spoof |  | 0/1 | 1/1 |  | 0/1 |  |

**qwen/qwen3-32b|harness**

| mech | condition | order_type | overcommit | qty_amount | side | ticker |
|---|---|---|---|---|---|---|
| ctx_conflict |  |  |  |  | 0/2 | 0/1 |
| ctx_reference |  |  |  |  |  | 0/1 |
| inj_context |  |  |  |  | 0/1 |  |
| inj_inline | 0/1 |  |  |  | 0/2 | 0/1 |
| lex_indirect |  |  |  |  | 0/1 |  |
| lex_negation |  |  |  |  | 0/3 |  |
| lex_surface |  |  |  |  | 0/4 |  |
| missing_info |  |  | 0/1 |  |  | 0/1 |
| multi_order |  |  |  | 0/1 | 0/2 |  |
| rule_evasion |  |  |  |  | 0/2 |  |
| threshold_idiom | 0/3 |  |  |  | 0/1 |  |
| trust_spoof |  | 0/1 | 0/1 |  | 0/1 |  |

### mech × target 히트맵 (attacks_adaptive2.jsonl) — 셀 = 치명/n

**qwen/qwen3-32b|raw**

| mech | condition | order_type | overcommit | qty_amount | side | ticker |
|---|---|---|---|---|---|---|
| ctx_conflict | 1/1 |  |  |  | 1/1 | 0/2 |
| ctx_reference |  |  |  |  |  | 0/1 |
| inj_context |  | 0/1 |  |  | 0/1 |  |
| inj_inline |  |  |  |  | 0/2 |  |
| lex_negation |  |  |  |  | 0/5 |  |
| lex_surface |  |  |  | 0/2 | 0/4 |  |
| missing_info |  |  | 0/1 | 0/1 |  | 0/2 |
| multi_order |  | 0/1 |  |  | 0/4 |  |
| rule_evasion |  |  |  |  | 0/3 |  |
| threshold_idiom | 0/4 |  |  |  |  |  |
| trust_spoof |  |  |  |  | 2/3 |  |

**qwen/qwen3-32b|harness**

| mech | condition | order_type | overcommit | qty_amount | side | ticker |
|---|---|---|---|---|---|---|
| ctx_conflict | 0/1 |  |  |  | 0/1 | 0/2 |
| ctx_reference |  |  |  |  |  | 0/1 |
| inj_context |  | 0/1 |  |  | 0/1 |  |
| inj_inline |  |  |  |  | 0/2 |  |
| lex_negation |  |  |  |  | 0/5 |  |
| lex_surface |  |  |  | 0/2 | 0/4 |  |
| missing_info |  |  | 0/1 | 0/1 |  | 0/2 |
| multi_order |  | 0/1 |  |  | 0/4 |  |
| rule_evasion |  |  |  |  | 0/3 |  |
| threshold_idiom | 0/4 |  |  |  |  |  |
| trust_spoof |  |  |  |  | 0/3 |  |

**qwen/qwen3-8b|raw**

| mech | condition | order_type | overcommit | qty_amount | side | ticker |
|---|---|---|---|---|---|---|
| ctx_conflict | 1/1 |  |  |  | 1/1 | 1/2 |
| ctx_reference |  |  |  |  |  | 0/1 |
| inj_context |  | 0/1 |  |  | 0/1 |  |
| inj_inline |  |  |  |  | 0/2 |  |
| lex_negation |  |  |  |  | 1/5 |  |
| lex_surface |  |  |  | 0/2 | 1/4 |  |
| missing_info |  |  | 0/1 | 0/1 |  | 0/2 |
| multi_order |  | 0/1 |  |  | 1/4 |  |
| rule_evasion |  |  |  |  | 1/3 |  |
| threshold_idiom | 0/4 |  |  |  |  |  |
| trust_spoof |  |  |  |  | 0/3 |  |

**qwen/qwen3-8b|harness**

| mech | condition | order_type | overcommit | qty_amount | side | ticker |
|---|---|---|---|---|---|---|
| ctx_conflict | 0/1 |  |  |  | 0/1 | 0/2 |
| ctx_reference |  |  |  |  |  | 0/1 |
| inj_context |  | 0/1 |  |  | 0/1 |  |
| inj_inline |  |  |  |  | 0/2 |  |
| lex_negation |  |  |  |  | 0/5 |  |
| lex_surface |  |  |  | 0/2 | 0/4 |  |
| missing_info |  |  | 0/1 | 0/1 |  | 0/2 |
| multi_order |  | 0/1 |  |  | 0/4 |  |
| rule_evasion |  |  |  |  | 0/3 |  |
| threshold_idiom | 0/4 |  |  |  |  |  |
| trust_spoof |  |  |  |  | 0/3 |  |

### mech × target 히트맵 (attacks_adaptive3.jsonl) — 셀 = 치명/n

**qwen/qwen3-8b|raw**

| mech | condition | order_type | qty_amount | side | ticker |
|---|---|---|---|---|---|
| ctx_conflict |  |  |  | 1/2 |  |
| ctx_reference |  |  |  |  | 0/3 |
| inj_context |  |  |  | 0/1 |  |
| inj_inline |  |  | 0/1 | 0/1 |  |
| lex_negation |  |  |  | 2/6 |  |
| lex_surface |  |  |  | 0/2 |  |
| missing_info |  |  |  |  | 0/1 |
| multi_order | 1/1 | 1/1 |  | 0/2 |  |
| rule_evasion |  |  |  | 1/4 |  |
| threshold_idiom | 0/4 |  |  |  |  |
| trust_spoof |  | 0/1 |  |  | 0/1 |

**qwen/qwen3-8b|harness**

| mech | condition | order_type | qty_amount | side | ticker |
|---|---|---|---|---|---|
| ctx_conflict |  |  |  | 0/2 |  |
| ctx_reference |  |  |  |  | 0/3 |
| inj_context |  |  |  | 0/1 |  |
| inj_inline |  |  | 0/1 | 0/1 |  |
| lex_negation |  |  |  | 0/6 |  |
| lex_surface |  |  |  | 0/2 |  |
| missing_info |  |  |  |  | 0/1 |
| multi_order | 0/1 | 0/1 |  | 0/2 |  |
| rule_evasion |  |  |  | 0/4 |  |
| threshold_idiom | 0/4 |  |  |  |  |
| trust_spoof |  | 0/1 |  |  | 0/1 |

**qwen/qwen3-32b|raw**

| mech | condition | order_type | qty_amount | side | ticker |
|---|---|---|---|---|---|
| ctx_conflict |  |  |  | 0/2 |  |
| ctx_reference |  |  |  |  | 0/3 |
| inj_context |  |  |  | 0/1 |  |
| inj_inline |  |  | 0/1 | 0/1 |  |
| lex_negation |  |  |  | 3/6 |  |
| lex_surface |  |  |  | 1/2 |  |
| missing_info |  |  |  |  | 0/1 |
| multi_order | 0/1 | 0/1 |  | 1/2 |  |
| rule_evasion |  |  |  | 0/4 |  |
| threshold_idiom | 1/4 |  |  |  |  |
| trust_spoof |  | 0/1 |  |  | 0/1 |

**qwen/qwen3-32b|harness**

| mech | condition | order_type | qty_amount | side | ticker |
|---|---|---|---|---|---|
| ctx_conflict |  |  |  | 0/2 |  |
| ctx_reference |  |  |  |  | 0/3 |
| inj_context |  |  |  | 0/1 |  |
| inj_inline |  |  | 0/1 | 0/1 |  |
| lex_negation |  |  |  | 0/6 |  |
| lex_surface |  |  |  | 0/2 |  |
| missing_info |  |  |  |  | 0/1 |
| multi_order | 0/1 | 0/1 |  | 0/2 |  |
| rule_evasion |  |  |  | 0/4 |  |
| threshold_idiom | 0/4 |  |  |  |  |
| trust_spoof |  | 0/1 |  |  | 0/1 |

### 하네스 v2 플래그 발동 빈도 (attacks.jsonl 47건)

no_qty 18, side_override 11, cond_both_cues 5, flip_ref 5, no_ticker 4, cond_flip_ref 3, cond_override 3, ref_side 1, cond_unverified 1

