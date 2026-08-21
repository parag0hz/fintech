#!/usr/bin/env python3
"""
공격자(프론티어)×방어자(Qwen raw/harness) ASR 매트릭스.
각 프론티어가 생성한 자기 공격 세트를 Qwen 방어자에 던져,
치명오류율(ASR = 확정했는데 방향 틀린 비율)을 잰다. 낮을수록 방어자가 강함.

v2 변경: 케이스별 원시 행 저장(--rows-out), 실패콜 수를 결과에 기록, 하네스 v1/v2 선택, TAXONOMY 태그가 있으면
mech×target 히트맵도 집계. 기본 코퍼스는 attacks_frontier9.jsonl(정본).

사용:
  py -3 run_asr.py --defenders qwen/qwen3-8b qwen/qwen3-32b
  py -3 run_asr.py --attacks attacks_adaptive.jsonl --harness v1 --out asr_adaptive_v1.json
"""
import os, sys, json, argparse, time, importlib
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from run import load_key, call_openrouter, normalize
from run_harness import hscore, load_tags, v1_case

HERE = os.path.dirname(os.path.abspath(__file__))


def raw_parse(model, case, key, retries=4):
    """성공 시 (pred_dict, None), 실패 시 (None, err). 실패를 절대 '오주문'으로 세지 않는다.
    raw 는 구 형식(history 도 [배경 정보] 한 덩어리)."""
    case = v1_case(case)
    err = None
    for a in range(retries):
        try:
            raw, _ = call_openrouter(model, case.get("context"), case["nl"], key)
            return normalize(raw), None
        except Exception as e:
            err = str(e)[:120]
            time.sleep(1.5 * (a + 1))
    return None, err


def harness_parse_ok(hmod, version, model, case, key, flip_policy, retries=4):
    err = None
    for a in range(retries):
        if version == "v1":
            final, flags, usage = hmod.harness_parse(model, v1_case(case), key)
            hx = {"parsed": None, "final": final, "flags": flags, "usage": usage}
        else:
            hx = hmod.harness_parse_ex(model, case, key, flip_policy=flip_policy)
        if not hx["usage"].get("_err"):
            return hx, None
        err = hx["usage"]["_err"]
        time.sleep(1.5 * (a + 1))
    return None, err


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--attacks", default=os.path.join(HERE, "attacks_frontier9.jsonl"))
    ap.add_argument("--tags", default=None)
    ap.add_argument("--defenders", nargs="+", default=["qwen/qwen3-8b", "qwen/qwen3-32b"])
    ap.add_argument("--harness", default="v2", choices=["v1", "v2"])
    ap.add_argument("--flip-policy", default="commit", choices=["commit", "confirm"])
    ap.add_argument("--out", default=None)
    ap.add_argument("--rows-out", default=None)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    key = load_key()
    if not key:
        print("!! OPENROUTER_API_KEY 없음", file=sys.stderr); sys.exit(2)

    hmod = importlib.import_module("harness_v1" if args.harness == "v1" else "harness")
    stem = os.path.basename(args.attacks).replace("attacks_", "").replace(".jsonl", "")
    suffix = "" if args.harness == "v2" else "_v1"
    out = args.out or os.path.join(HERE, "asr_%s%s.json" % (stem, suffix))
    rows_out = args.rows_out or os.path.join(HERE, "asr_rows_%s%s.json" % (stem, suffix))
    tags = load_tags(args.tags or os.path.join(HERE, "tags_%s.jsonl" % stem))

    cases = [json.loads(l) for l in open(args.attacks, encoding="utf-8") if l.strip()]
    if not cases:
        print("!! 케이스 없음:", args.attacks, file=sys.stderr); sys.exit(2)
    for c in cases:
        c.setdefault("attacker", "unknown")
    by_attacker = defaultdict(list)
    for c in cases:
        by_attacker[c["attacker"]].append(c)

    # (attacker, defender, mode) -> [critical, n_ok, over_abstain]
    res = defaultdict(lambda: [0, 0, 0])
    errors = defaultdict(int)   # (attacker,defender) -> 실패로 제외된 케이스 수
    rows = defaultdict(list)    # defender -> rows

    jobs = [(c, d) for c in cases for d in args.defenders]

    def work(job):
        c, d = job
        rp, rerr = raw_parse(d, c, key)
        hx, herr = harness_parse_ok(hmod, args.harness, d, c, key, args.flip_policy)
        row = {"id": c["id"], "attacker": c["attacker"], "cat": c.get("cat"), "gold": c["gold"],
               "raw_pred": rp, "raw_err": rerr,
               "h_parsed": hx and hx["parsed"], "h_final": hx and hx["final"], "h_flags": hx and hx["flags"], "h_err": herr}
        if rerr or herr:            # 둘 중 하나라도 호출 실패 → 이 케이스 제외(오주문으로 세지 않음)
            return d, row, None, None
        return d, row, hscore(rp, c["gold"]), hscore(hx["final"], c["gold"])

    print("· 워밍업 %d defenders" % len(args.defenders))
    for d in args.defenders:
        raw_parse(d, cases[0], key)

    print("· ASR 측정: %d cases × %d defenders (raw+harness %s), 실패콜은 제외" % (len(cases), len(args.defenders), args.harness))
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for f in as_completed([ex.submit(work, j) for j in jobs]):
            d, row, rs, hs = f.result()
            row["raw_score"], row["h_score"] = rs, hs
            rows[d].append(row)
            att = row["attacker"]
            if rs is None:
                errors[(att, d)] += 1
                continue
            for mode, s in (("raw", rs), ("harness", hs)):
                k = (att, d, mode)
                res[k][0] += s["critical"]; res[k][1] += 1; res[k][2] += s["unnec_abstain"]
    if errors:
        print("  제외된 실패콜:", {("%s/%s" % (a.split('/')[-1], d.split('/')[-1])): n for (a, d), n in errors.items()})

    # mech × target 히트맵 (defender × mode)
    heat = {}
    if tags:
        for d, rs_ in rows.items():
            for mode in ("raw", "harness"):
                h = {}
                for r in rs_:
                    s = r["raw_score" if mode == "raw" else "h_score"]; t = tags.get(r["id"])
                    if s is None or not t:
                        continue
                    cell = h.setdefault(t["mech"], {}).setdefault(t["target"], [0, 0])
                    cell[1] += 1; cell[0] += int(s["critical"])
                heat["%s|%s" % (d, mode)] = h

    # 출력
    attackers = sorted(by_attacker)
    print("\n" + "=" * 80)
    print("ASR 매트릭스 — 공격자(프론티어) × 방어자(Qwen). 셀 = 치명오류율(과잉보류)  [harness %s]" % args.harness)
    print("=" * 80)
    header = "%-26s" % "attacker \\ defender"
    for d in args.defenders:
        header += "%-22s" % (d.split("/")[-1][:20])
    print(header)
    print("-" * 80)
    tot = defaultdict(lambda: [0, 0])
    for att in attackers:
        sname = att.split("/")[-1]
        n = len(by_attacker[att])
        line = "%-26s" % ("%s (%d건)" % (sname[:16], n))
        for d in args.defenders:
            rc = res[(att, d, "raw")]; hc = res[(att, d, "harness")]
            rrate = 100 * rc[0] / max(1, rc[1]); hrate = 100 * hc[0] / max(1, hc[1])
            line += "%-22s" % ("raw %.0f%%→har %.0f%%" % (rrate, hrate))
            tot[(d, "raw")][0] += rc[0]; tot[(d, "raw")][1] += rc[1]
            tot[(d, "harness")][0] += hc[0]; tot[(d, "harness")][1] += hc[1]
        print(line)
    line = "%-26s" % "전체(풀 집계)"
    for d in args.defenders:
        r_, h_ = tot[(d, "raw")], tot[(d, "harness")]
        line += "%-22s" % ("raw %.0f%%→har %.0f%%" % (100 * r_[0] / max(1, r_[1]), 100 * h_[0] / max(1, h_[1])))
    print(line)
    print("=" * 80)
    print("(치명오류율 = 방어자가 주문을 확정했는데 매수/매도 또는 이하/이상이 틀린 비율. 낮을수록 강함)")
    json.dump({"cells": {str(k): v for k, v in res.items()},
               "errors": {"%s|%s" % k: v for k, v in errors.items()},
               "heat_mech_target": heat, "harness": args.harness, "flip_policy": args.flip_policy,
               "attacks": os.path.basename(args.attacks), "defenders": args.defenders},
              open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump({"attacks": os.path.basename(args.attacks), "harness": args.harness, "rows": rows},
              open(rows_out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("집계 →", out, "\n원시 행 →", rows_out)


if __name__ == "__main__":
    main()
