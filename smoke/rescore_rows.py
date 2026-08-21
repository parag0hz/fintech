#!/usr/bin/env python3
"""
저장된 원시 행(harness_rows*.json / asr_rows_*.json)을 API 재호출 없이 재계산한다.
  - v2 행: 저장된 모델 출력(h_parsed)에 현재 harness.deterministic_check(L3) 를 다시 적용 → h_final/h_flags 갱신
           (L3 는 결정적이고 L2 프롬프트가 안 바뀌었을 때만 유효 — 프롬프트를 바꿨으면 run_harness/run_asr 를 다시 돌릴 것)
  - v1 행: h_final 유지(v1 은 재계산 안 함)
  - 모든 행: 코퍼스의 현재 gold 로 raw_score/h_score 재채점(gold adjudication 반영)
  - 집계 파일(harness_results*.json, asr_*.json) 재생성

  py -3 rescore_rows.py                 # smoke/ 안의 알려진 파일 전부
"""
import os, sys, json, io, glob, re
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from harness import deterministic_check
from run_harness import hscore, agg, agg_mt, load_tags

CORPUS = {"attacks.jsonl": "attacks", "attacks_frontier9.jsonl": "frontier9", "attacks_adaptive.jsonl": "adaptive"}


def load_cases(fn):
    p = os.path.join(HERE, fn)
    if not os.path.exists(p):
        return {}
    return {c["id"]: c for c in (json.loads(l) for l in open(p, encoding="utf-8") if l.strip())}


def rescore_row(r, case, harness):
    r["gold"] = case["gold"]
    if harness == "v2" and r.get("h_parsed") is not None:
        final, flags, detail = deterministic_check(case["nl"], case.get("history"), r["h_parsed"])
        r["h_final"], r["h_flags"] = final, flags
        r["h_detail"] = {k: v for k, v in detail.items() if k in ("side", "cond", "side_both", "cond_both", "flip_side", "flip_cond", "history", "hesitation")}
    if r.get("raw_score") is not None or r.get("raw_pred") is not None:
        r["raw_score"] = hscore(r.get("raw_pred"), case["gold"]) if not r.get("raw_err") else r.get("raw_score")
    if r.get("h_final") is not None and not r.get("h_err"):
        r["h_score"] = hscore(r["h_final"], case["gold"])


def do_harness_rows(path):
    d = json.load(open(path, encoding="utf-8"))
    fn = os.path.basename(d.get("cases", "attacks.jsonl"))
    cases = load_cases(fn)
    tags = load_tags(os.path.join(HERE, "tags_%s.jsonl" % CORPUS.get(fn, "attacks")))
    harness = d.get("harness", "v2")
    report = {}
    for model, rows in d["rows"].items():
        for r in rows:
            if r["id"] in cases:
                rescore_row(r, cases[r["id"]], harness)
        raw_pairs = [(r["cat"], r["raw_score"]) for r in rows]
        h_pairs = [(r["cat"], r["h_score"]) for r in rows]
        fc = {}
        for r in rows:
            for fl in r["h_flags"] or []:
                fc[fl.split("→")[0]] = fc.get(fl.split("→")[0], 0) + 1
        rc, ru, rb = agg(raw_pairs); hc, hu, hb = agg(h_pairs)
        report[model] = {"raw_crit": rc, "raw_unnec": ru, "h_crit": hc, "h_unnec": hu,
                         "raw_err": sum(1 for r in rows if r.get("raw_err")), "h_err": sum(1 for r in rows if r.get("h_err")),
                         "raw_bycat": rb, "h_bycat": hb, "flags": fc, "h_mech_target": agg_mt(rows, tags),
                         "harness": harness, "n": len(rows), "rescored": True}
    json.dump(d, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    outp = path.replace("harness_rows", "harness_results")
    json.dump(report, open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("%-28s → %s" % (os.path.basename(path), os.path.basename(outp)))
    for m, r in report.items():
        print("   %-28s raw %d(%d) → h %d(%d)" % (m, r["raw_crit"], r["raw_unnec"], r["h_crit"], r["h_unnec"]))


def do_asr_rows(path):
    d = json.load(open(path, encoding="utf-8"))
    fn = d.get("attacks", "attacks_frontier9.jsonl")
    cases = load_cases(fn)
    stem = CORPUS.get(fn, fn.replace("attacks_", "").replace(".jsonl", ""))
    tags = load_tags(os.path.join(HERE, "tags_%s.jsonl" % stem))
    harness = d.get("harness", "v2")
    res = defaultdict(lambda: [0, 0, 0]); errors = defaultdict(int); heat = {}
    for dfd, rows in d["rows"].items():
        for r in rows:
            if r["id"] in cases:
                rescore_row(r, cases[r["id"]], harness)
            att = r.get("attacker", "unknown")
            if r.get("raw_err") or r.get("h_err") or r.get("raw_score") is None:
                errors[(att, dfd)] += 1; continue
            for mode, s in (("raw", r["raw_score"]), ("harness", r["h_score"])):
                k = (att, dfd, mode); res[k][0] += s["critical"]; res[k][1] += 1; res[k][2] += s["unnec_abstain"]
        for mode in ("raw", "harness"):
            h = {}
            for r in rows:
                s = r.get("raw_score" if mode == "raw" else "h_score"); t = tags.get(r["id"])
                if s is None or not t:
                    continue
                cell = h.setdefault(t["mech"], {}).setdefault(t["target"], [0, 0]); cell[1] += 1; cell[0] += int(s["critical"])
            heat["%s|%s" % (dfd, mode)] = h
    json.dump(d, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    outp = path.replace("asr_rows_", "asr_")
    old = json.load(open(outp, encoding="utf-8")) if os.path.exists(outp) else {}
    old.update({"cells": {str(k): v for k, v in res.items()}, "errors": {"%s|%s" % k: v for k, v in errors.items()},
                "heat_mech_target": heat, "harness": harness, "attacks": fn, "defenders": list(d["rows"]), "rescored": True})
    json.dump(old, open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("%-28s → %s" % (os.path.basename(path), os.path.basename(outp)))
    tot = defaultdict(lambda: [0, 0])
    for (att, dfd, mode), v in res.items():
        tot[(dfd, mode)][0] += v[0]; tot[(dfd, mode)][1] += v[1]
    for dfd in d["rows"]:
        r_, h_ = tot[(dfd, "raw")], tot[(dfd, "harness")]
        print("   %-20s raw %d/%d=%.1f%% → harness %d/%d=%.1f%%" % (dfd.split("/")[-1], r_[0], r_[1], 100 * r_[0] / max(1, r_[1]), h_[0], h_[1], 100 * h_[0] / max(1, h_[1])))


if __name__ == "__main__":
    for p in sorted(glob.glob(os.path.join(HERE, "harness_rows*.json"))):
        do_harness_rows(p)
    for p in sorted(glob.glob(os.path.join(HERE, "asr_rows_*.json"))):
        do_asr_rows(p)
