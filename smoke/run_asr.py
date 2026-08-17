#!/usr/bin/env python3
"""
공격자(프론티어)×방어자(Qwen raw/harness) ASR 매트릭스.
각 프론티어가 생성한 자기 공격 세트를 Qwen 방어자에 던져,
치명오류율(ASR = 확정했는데 방향 틀린 비율)을 잰다. 낮을수록 방어자가 강함.
"""
import os, sys, json, argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from run import load_key, call_openrouter, normalize
from run_harness import hscore
from harness import harness_parse

HERE = os.path.dirname(os.path.abspath(__file__))


import time


def raw_parse(model, case, key, retries=4):
    """성공 시 (pred_dict, True), 실패 시 (None, False). 실패를 절대 '오주문'으로 세지 않는다."""
    for a in range(retries):
        try:
            raw, _ = call_openrouter(model, case.get("context"), case["nl"], key)
            return normalize(raw), True
        except Exception:
            time.sleep(1.5 * (a + 1))
    return None, False


def harness_parse_ok(model, case, key, retries=4):
    for a in range(retries):
        final, flags, usage = harness_parse(model, case, key)
        if not usage.get("_err"):
            return final, True
        time.sleep(1.5 * (a + 1))
    return None, False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--attacks", default=os.path.join(HERE, "attacks_frontier_all.jsonl"))
    ap.add_argument("--defenders", nargs="+", default=["qwen/qwen3-8b", "qwen/qwen3-14b"])
    ap.add_argument("--out", default=os.path.join(HERE, "asr_matrix.json"))
    args = ap.parse_args()
    key = load_key()
    if not key:
        print("!! OPENROUTER_API_KEY 없음", file=sys.stderr); sys.exit(2)

    cases = [json.loads(l) for l in open(args.attacks)]
    by_attacker = defaultdict(list)
    for c in cases:
        by_attacker[c["attacker"]].append(c)

    # (attacker, defender, mode) -> [critical, n_ok, over_abstain]
    res = defaultdict(lambda: [0, 0, 0])
    errors = defaultdict(int)   # (attacker,defender) -> 실패로 제외된 케이스 수

    jobs = []
    for c in cases:
        for d in args.defenders:
            jobs.append((c, d))

    def work(job):
        c, d = job
        rp, rok = raw_parse(d, c, key)
        hp, hok = harness_parse_ok(d, c, key)
        if not (rok and hok):       # 둘 중 하나라도 호출 실패 → 이 케이스 제외(오주문으로 세지 않음)
            return (c["attacker"], d, None, None)
        return (c["attacker"], d, hscore(rp, c["gold"]), hscore(hp, c["gold"]))

    print("· 워밍업 %d defenders" % len(args.defenders))
    for d in args.defenders:
        raw_parse(d, cases[0], key)

    print("· ASR 측정: %d cases × %d defenders (raw+harness), 실패콜은 제외" % (len(cases), len(args.defenders)))
    with ThreadPoolExecutor(max_workers=4) as ex:
        for f in as_completed([ex.submit(work, j) for j in jobs]):
            att, d, rs, hs = f.result()
            if rs is None:
                errors[(att, d)] += 1
                continue
            for mode, s in (("raw", rs), ("harness", hs)):
                k = (att, d, mode)
                res[k][0] += s["critical"]; res[k][1] += 1; res[k][2] += s["unnec_abstain"]
    if errors:
        print("  제외된 실패콜:", {("%s/%s" % (a.split('/')[-1], d.split('/')[-1])): n for (a, d), n in errors.items()})

    # 출력
    attackers = sorted(by_attacker)
    print("\n" + "=" * 80)
    print("ASR 매트릭스 — 공격자(프론티어) × 방어자(Qwen). 셀 = 치명오류율(과잉보류)")
    print("=" * 80)
    header = "%-26s" % "attacker \\ defender"
    for d in args.defenders:
        header += "%-22s" % (d.split("/")[-1][:20])
    print(header)
    print("-" * 80)
    for att in attackers:
        sname = att.split("/")[-1]
        n = len(by_attacker[att])
        line = "%-26s" % ("%s (%d건)" % (sname[:16], n))
        for d in args.defenders:
            rc = res[(att, d, "raw")]; hc = res[(att, d, "harness")]
            rrate = 100 * rc[0] / max(1, rc[1]); hrate = 100 * hc[0] / max(1, hc[1])
            cell = "raw %.0f%%→har %.0f%%" % (rrate, hrate)
            line += "%-22s" % cell
        print(line)
    print("=" * 80)
    print("(치명오류율 = 방어자가 주문을 확정했는데 매수/매도 또는 이하/이상이 틀린 비율. 낮을수록 강함)")
    json.dump({str(k): v for k, v in res.items()}, open(args.out, "w"), ensure_ascii=False, indent=2)
    print("상세 →", args.out)


if __name__ == "__main__":
    main()
