#!/usr/bin/env python3
"""
phrasebook(실사용자 표현) 평가 — harness_rows_phrasebook.json(run_harness 산출) 기준.
  치명오류율   = 확정했는데 side/condition 이 gold 와 다름 (committed-gated)
  확인요청률   = gold 는 확정 주문인데 하네스가 보류(abstain) — 사용성 비용
  근거 인용 on/off 비교: 저장된 모델 출력(h_parsed)에서 side_evidence/condition_evidence 를 지우고 L3 를 다시 돌린 값 = off
  스타일별·raw 대비 표.  py -3 eval_phrasebook.py [rows.json]
"""
import os, sys, json, io
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from harness import deterministic_check
from run_harness import hscore

args = [x for x in sys.argv[1:] if not x.startswith("--")]
WITH_POS = "--with-positions" in sys.argv     # 실제 앱처럼 '말한 종목을 보유 중'이라고 가정(수량 100, 평단 250,000)
rows_path = args[0] if args else os.path.join(HERE, "harness_rows_phrasebook.json")
d = json.load(open(rows_path, encoding="utf-8"))
cases = {c["id"]: c for c in (json.loads(l) for l in open(os.path.join(HERE, "attacks_phrasebook.jsonl"), encoding="utf-8") if l.strip())}
if WITH_POS:
    for c in cases.values():
        t = (c.get("gold") or {}).get("ticker")
        if t and not c.get("positions"):
            c["positions"] = [{"ticker": t, "quantity": 100, "avg_price": 250000}]
    print("(positions 가정: 말한 종목 100주 보유, 평단 250,000)")

for model, rows in d["rows"].items():
    print("== %s  (%d건)" % (model, len(rows)))
    agg = defaultdict(lambda: defaultdict(int))     # style -> metric -> count
    tot = defaultdict(int)
    for r in rows:
        c = cases.get(r["id"]); g = r["gold"]
        if not c:
            continue
        st = c.get("style", "?")
        gold_commit = not g.get("abstain")
        # raw
        rs = r["raw_score"] or {}
        # harness on = 현행 규칙으로 재계산(근거 인용 유지). 저장된 h_score 는 측정 당시 규칙이라 참고만.
        parsed_on = dict(r["h_parsed"] or {})
        f_on, fl_on, _ = deterministic_check(c["nl"], c.get("history"), parsed_on, positions=c.get("positions"))
        hs = hscore(f_on, g)
        r["h_final"], r["h_flags"] = f_on, fl_on
        # harness off-evidence (재계산)
        parsed = dict(r["h_parsed"] or {})
        parsed.pop("side_evidence", None); parsed.pop("condition_evidence", None)
        f_off, fl_off, _ = deterministic_check(c["nl"], c.get("history"), parsed, positions=c.get("positions"))
        os_ = hscore(f_off, g)
        # pct 정답(트리거가) 확인
        pct_ok = None
        if c.get("gold_pct") and r.get("h_final"):
            gp = c["gold_pct"]; ref = gp.get("ref_price"); pct = gp.get("pct"); kind = gp.get("kind")
            if ref and pct:
                exp = int(ref * (1 - pct / 100.0) + 0.5) if kind == "LOSS" else int(ref * (1 + pct / 100.0) + 0.5)
                pct_ok = (r["h_final"].get("trigger_price") == exp)
        for key, s in (("raw", rs), ("on", hs), ("off", os_)):
            agg[st]["n"] += 0
            tot[key + "_n"] += 1
            if s.get("critical"):
                agg[st][key + "_crit"] += 1; tot[key + "_crit"] += 1
            if gold_commit and s.get("unnec_abstain"):
                agg[st][key + "_confirm"] += 1; tot[key + "_confirm"] += 1
        agg[st]["n"] += 1
        if gold_commit:
            agg[st]["gc"] += 1; tot["gc"] += 1
        if pct_ok is not None:
            tot["pct_n"] += 1; tot["pct_ok"] += int(pct_ok)
        if hs.get("critical"):
            print("   CRIT(on)  %-24s %-8s %s | final %s/%s gold %s/%s | %s" % (r["id"], st, c["nl"][:50], r["h_final"].get("side"), r["h_final"].get("condition"), g.get("side"), g.get("condition"), r["h_flags"]))
    n = tot["raw_n"]; gc = max(1, tot["gc"])
    print("\n  %-14s %8s %10s %10s" % ("", "raw", "하네스(근거off)", "하네스(근거on)"))
    print("  %-14s %7.1f%% %10.1f%% %10.1f%%   (n=%d)" % ("치명오류율", 100 * tot["raw_crit"] / n, 100 * tot["off_crit"] / n, 100 * tot["on_crit"] / n, n))
    print("  %-14s %7.1f%% %10.1f%% %10.1f%%   (gold 확정 %d건 중)" % ("확인요청률", 100 * tot["raw_confirm"] / gc, 100 * tot["off_confirm"] / gc, 100 * tot["on_confirm"] / gc, tot["gc"]))
    if tot["pct_n"]:
        print("  %-14s %d/%d" % ("퍼센트 트리거 정답", tot["pct_ok"], tot["pct_n"]))
    print("\n  스타일별 (n · gold확정 · raw치명/확인 · off치명/확인 · on치명/확인)")
    for st in sorted(agg, key=lambda s: -agg[s]["n"]):
        a = agg[st]
        print("   %-20s %3d %3d   %2d/%-2d   %2d/%-2d   %2d/%-2d" % (st, a["n"], a["gc"], a["raw_crit"], a["raw_confirm"], a["off_crit"], a["off_confirm"], a["on_crit"], a["on_confirm"]))
