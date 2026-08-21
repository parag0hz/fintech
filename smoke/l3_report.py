#!/usr/bin/env python3
"""L3(결정적 검증)만의 커버리지 리포트 — 모델 없이. 뒤집힌 입력을 못 복원한 케이스와 과잉보류 케이스를 나열.
py -3 l3_report.py attacks.jsonl attacks_frontier9.jsonl"""
import sys, json, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import deterministic_check
from run_harness import hscore


def _load(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def _flip(g):
    x = dict(g)
    if x.get("side") in ("BUY", "SELL"):
        x["side"] = "SELL" if x["side"] == "BUY" else "BUY"
    if x.get("condition") in ("LE", "GE"):
        x["condition"] = "GE" if x["condition"] == "LE" else "LE"
    x["abstain"] = False
    return x


for path in sys.argv[1:]:
    cases = _load(path)
    print("== %s (%d)" % (path, len(cases)))
    for c in cases:
        g = c["gold"]
        f, fl, a = deterministic_check(c["nl"], c.get("history"), dict(g))
        s = hscore(f, g)
        if s["unnec_abstain"]:
            print("  과잉보류  %-20s %s | flags=%s" % (c["id"], c["nl"][:50], fl))
        if g.get("side") in ("BUY", "SELL") or g.get("condition") in ("LE", "GE"):
            f2, fl2, _ = deterministic_check(c["nl"], c.get("history"), _flip(g))
            s2 = hscore(f2, g)
            if s2["critical"]:
                print("  잔존(뒤집힘 미복원) %-20s %s | side %s→%s cond %s→%s | flags=%s"
                      % (c["id"], c["nl"][:44], f2.get("side"), g.get("side"), f2.get("condition"), g.get("condition"), fl2))
