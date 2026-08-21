#!/usr/bin/env python3
"""
실험1 결과 파일(results_full.json / results_q25.json)의 summary 를 현행 채점기(run.score, 정규화 포함)로 재생성한다.
(구 정규화기로 저장된 summary 가 stale 이었음: qwen3-30b-a3b 11/14, opus 6/33 → 재채점 6/15, 3/34)
전부 실패콜(err)인 모델은 요약에 `all_failed: true` 를 표시한다.

  py -3 resummarize.py            # 두 파일 제자리 갱신 + 콘솔 표
"""
import os, sys, json, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from run import score, summarize, print_table

for fn in ("results_full.json", "results_q25.json"):
    p = os.path.join(HERE, fn)
    if not os.path.exists(p):
        continue
    d = json.load(open(p, encoding="utf-8"))
    sums = []
    for m, rows in d["rows"].items():
        for r in rows:
            r["score"] = score(r["pred"], r["gold"]) if r.get("err") is None else \
                {"exact": False, "critical": True, "field_hits": 0, "n_fields": 8, "abstain_ok": False}
        s = summarize(m, rows)
        s["all_failed"] = all(r.get("err") for r in rows)
        s["rescored"] = True
        sums.append(s)
    d["summaries"] = sums
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("\n== %s (재채점)" % fn)
    print_table(sums)
    for s in sums:
        if s["all_failed"]:
            print("  !! %s: 전부 실패콜(모델 ID 오류 등) — 표에서 제외할 것" % s["model"])
