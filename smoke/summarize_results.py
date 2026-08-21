#!/usr/bin/env python3
"""
결과 JSON → 마크다운 표. RESULTS.md 의 숫자는 전부 이 출력에서 가져온다(추적 가능).
  py -3 summarize_results.py            # 콘솔에 마크다운 출력
  py -3 summarize_results.py > tables.md
"""
import os, sys, json, io, glob, re
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))


def J(fn):
    p = os.path.join(HERE, fn)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def short(m):
    return m.split("/")[-1]


def exp1():
    print("### 실험1 — raw 벤치 (attacks.jsonl 47건, run.score: 파싱실패 포함·보류 비게이트)\n")
    print("| 방어자 | 치명오류 /47 | 완전일치 /47 | 필드정확도 | p50 ms |\n|---|---|---|---|---|")
    for fn in ("results_full.json", "results_q25.json"):
        d = J(fn)
        if not d:
            continue
        for s in d["summaries"]:
            if s.get("all_failed"):
                continue
            print("| %s | %d | %d | %.1f%% | %d |" % (short(s["model"]), s["crit"], s["exact"], 100 * s["field_acc"], s["p50ms"]))
    print()


def exp2():
    v2, v1 = J("harness_results.json"), J("harness_results_v1.json")
    if not v2:
        return
    print("### 실험2 — raw vs 하네스 (attacks.jsonl 47건, committed-gated 치명; 괄호 = 과잉보류)\n")
    hdr = "| 방어자 | raw | 하네스 v1 | 하네스 v2 |" if v1 else "| 방어자 | raw | 하네스 v2 |"
    print(hdr + "\n" + "|---" * (4 if v1 else 3) + "|")
    for m, r in v2.items():
        cells = ["%d(%d)" % (r["raw_crit"], r["raw_unnec"])]
        if v1 and m in v1:
            cells.append("%d(%d)" % (v1[m]["h_crit"], v1[m]["h_unnec"]))
        elif v1:
            cells.append("—")
        cells.append("%d(%d)" % (r["h_crit"], r["h_unnec"]))
        print("| %s | %s |" % (short(m), " | ".join(cells)))
    print()
    # 카테고리별 잔존(v2)
    cats = [c for c in next(iter(v2.values()))["h_bycat"] if next(iter(v2.values()))["h_bycat"][c][1]]
    print("v2 카테고리별 치명(raw→h): " + "; ".join(
        "%s: " % short(m) + ", ".join("%s %d→%d/%d" % (c, r["raw_bycat"][c][0], r["h_bycat"][c][0], r["h_bycat"][c][1]) for c in cats if r["raw_bycat"][c][0] or r["h_bycat"][c][0])
        for m, r in v2.items()) + "\n")


def parse_key(k):
    m = re.match(r"\('([^']+)', '([^']+)', '(\w+)'\)", k)
    return m.groups()


def asr(fn, title):
    d = J(fn)
    if not d or "cells" not in d:
        return
    cells = {parse_key(k): v for k, v in d["cells"].items()}
    defenders = d.get("defenders") or sorted({k[1] for k in cells})
    attackers = sorted({k[0] for k in cells})
    print("### %s (%s, harness %s)\n" % (title, d.get("attacks"), d.get("harness")))
    print("| 공격자 | " + " | ".join(short(x) + " raw→하네스" for x in defenders) + " |")
    print("|---" * (len(defenders) + 1) + "|")
    tot = defaultdict(lambda: [0, 0])
    for a in attackers:
        row = []
        n = None
        for dfd in defenders:
            r_, h_ = cells.get((a, dfd, "raw"), [0, 0, 0]), cells.get((a, dfd, "harness"), [0, 0, 0])
            n = r_[1]
            row.append("%.0f%% → %.0f%% (n=%d, 과잉 %d→%d)" % (100 * r_[0] / max(1, r_[1]), 100 * h_[0] / max(1, h_[1]), r_[1], r_[2], h_[2]))
            tot[(dfd, "raw")][0] += r_[0]; tot[(dfd, "raw")][1] += r_[1]; tot[(dfd, "harness")][0] += h_[0]; tot[(dfd, "harness")][1] += h_[1]
        print("| %s | %s |" % (short(a), " | ".join(row)))
    row = []
    for dfd in defenders:
        r_, h_ = tot[(dfd, "raw")], tot[(dfd, "harness")]
        row.append("**%.1f%% → %.1f%%** (%d/%d → %d/%d)" % (100 * r_[0] / max(1, r_[1]), 100 * h_[0] / max(1, h_[1]), r_[0], r_[1], h_[0], h_[1]))
    print("| **전체(풀 집계)** | %s |" % " | ".join(row))
    if d.get("errors"):
        print("\n제외된 실패콜: %s" % d["errors"])
    print()


def heat(fn):
    d = J(fn)
    if not d or not d.get("heat_mech_target"):
        return
    print("### mech × target 히트맵 (%s) — 셀 = 치명/n\n" % d.get("attacks"))
    for key, h in d["heat_mech_target"].items():
        targets = sorted({t for m in h.values() for t in m})
        print("**%s**\n" % key)
        print("| mech | " + " | ".join(targets) + " |")
        print("|---" * (len(targets) + 1) + "|")
        for mech, row in sorted(h.items()):
            print("| %s | %s |" % (mech, " | ".join(("%d/%d" % tuple(row[t])) if t in row else "" for t in targets)))
        print()


def flags():
    v2 = J("harness_results.json")
    if not v2:
        return
    print("### 하네스 v2 플래그 발동 빈도 (attacks.jsonl 47건)\n")
    allf = defaultdict(int)
    for r in v2.values():
        for k, n in r["flags"].items():
            allf[k] += n
    print(", ".join("%s %d" % (k, n) for k, n in sorted(allf.items(), key=lambda x: -x[1])) + "\n")


if __name__ == "__main__":
    exp1(); exp2()
    asr("asr_frontier9_v1.json", "실험4 — ASR 프론티어 코퍼스, 하네스 v1")
    asr("asr_frontier9.json", "실험4 — ASR 프론티어 코퍼스, 하네스 v2")
    asr("asr_adaptive_v1.json", "실험5 — ASR 적응형 1라운드(난이도 3), 하네스 v1")
    asr("asr_adaptive.json", "실험5 — ASR 적응형 1라운드(난이도 3), 하네스 v2 (현행 규칙으로 재채점 = in-sample)")
    asr("asr_adaptive2.json", "실험5 — ASR 적응형 2라운드(v2.1 규칙 공개), 하네스 v2 (현행 규칙 재채점; 측정 당시 값은 snapshots/v2.1 로그)")
    asr("asr_adaptive3.json", "실험5 — ASR 적응형 3라운드(v2.2 규칙 공개), 하네스 v2 (현행 규칙 재채점; 측정 당시 값은 snapshots/v2.2 로그)")
    heat("asr_frontier9.json"); heat("asr_adaptive.json"); heat("asr_adaptive2.json"); heat("asr_adaptive3.json")
    flags()
