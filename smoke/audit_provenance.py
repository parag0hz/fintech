#!/usr/bin/env python3
"""필드별 실행 근거 감사 — 확정된 주문에 '근거 없는 critical field' 가 남아 있는가.

왜: 하네스의 완전성 게이트는 "필드가 비었나"만 본다. 모델이 종목·수량·가격을 **지어내면**
    비어 있지 않으므로 게이트를 통과한다. provenance 는 "값이 있는가" 대신
    "그 값이 사용자 발화에서 왔는가"를 묻기 때문에 이 빈틈을 드러낸다.

무엇을 세나:
  unsupported critical field = 값이 있는데 USER_EXPLICIT/USER_DERIVED/TRUSTED_CONTEXT
                               어느 쪽에서도 오지 않은 필드(= MODEL_INFERRED)
  두 기준으로 센다:
    raw   — 모델 출력을 그대로 실행한다고 가정했을 때
    final — 하네스를 거쳐 **확정된(abstain=false)** 주문만

GPU·외부 LLM 호출 없음. 저장된 원시 행과 코퍼스만 사용한다.
실행: python3 audit_provenance.py [--json out.json]
"""
import argparse, json, os, sys, io
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from harness import deterministic_check, field_provenance, unsupported_critical_fields, CRITICAL_FIELDS

HERE = os.path.dirname(os.path.abspath(__file__))

# (라벨, 원시행 파일, 코퍼스 파일) — 원시행이 없으면 코퍼스의 gold 를 '완벽한 모델' 입력으로 쓴다
SETS = [
    ("자체작성 47",      "harness_rows_self47_v25.json", "attacks.jsonl"),
    ("프론티어 142",     "harness_rows_fr9_v25.json",    "attacks_frontier9.jsonl"),
    ("한국어 임계 88",   "harness_rows_ko_v25.json",     "attacks_ko_threshold.jsonl"),
    ("AgentDojo 72",    "harness_rows_adojo_v25.json",  "attacks_agentdojo_ko.jsonl"),
    ("BFCL 30",         "harness_rows_irr_v25.json",    "attacks_irrelevance_ko.jsonl"),
    ("일상어체 합성 240", "harness_rows_phrasebook.json", "attacks_phrasebook.jsonl"),
]


def load_jsonl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    report = {"sets": [], "note": "GPU·외부 호출 없이 저장된 원시 행에서 계산"}
    print("=" * 82)
    print("실행 근거 감사 — 확정된 주문에 근거 없는 critical field 가 남는가")
    print("=" * 82)
    print("%-18s %-7s %-22s %-22s" % ("코퍼스", "n", "raw 기준", "하네스 확정분 기준"))
    print("-" * 82)

    for label, rowf, cf in SETS:
        cpath, rpath = os.path.join(HERE, cf), os.path.join(HERE, rowf)
        if not os.path.exists(cpath):
            print("%-18s (코퍼스 없음 — 계산 불가)" % label); continue
        cases = {c["id"]: c for c in load_jsonl(cpath)}
        rows = None
        if os.path.exists(rpath):
            d = json.load(open(rpath, encoding="utf-8"))
            rows = list(d["rows"].values())[0] if isinstance(d, dict) and "rows" in d else None

        raw_bad, fin_bad, fin_n, n = Counter(), Counter(), 0, 0
        raw_cases, fin_cases = 0, 0
        examples = []
        for cid, c in cases.items():
            r = next((x for x in rows if x["id"] == cid), None) if rows else None
            model_out = (r or {}).get("h_parsed") or (r or {}).get("raw_pred") or c["gold"]
            if not isinstance(model_out, dict):
                continue
            n += 1
            # raw 기준 — 모델 출력을 그대로 실행한다고 가정
            prov_raw = field_provenance(c["nl"], model_out, [], parsed=model_out, history=c.get("history"))
            bad_raw = unsupported_critical_fields(prov_raw)
            if bad_raw:
                raw_cases += 1
                for k in bad_raw:
                    raw_bad[k] += 1
            # 하네스 확정분 기준
            f, flags, _ = deterministic_check(c["nl"], c.get("history") or [], dict(model_out))
            if f.get("abstain"):
                continue
            fin_n += 1
            prov = field_provenance(c["nl"], f, flags, parsed=model_out, history=c.get("history"))
            bad = unsupported_critical_fields(prov)
            if bad:
                fin_cases += 1
                for k in bad:
                    fin_bad[k] += 1
                if len(examples) < 4:
                    examples.append({"id": cid, "nl": c["nl"][:60], "fields": bad, "flags": flags})

        print("%-18s %-7s %-22s %-22s" % (
            label, n,
            "%d건 (%s)" % (raw_cases, ", ".join("%s %d" % x for x in raw_bad.most_common(3)) or "-"),
            "%d/%d 확정 (%s)" % (fin_cases, fin_n, ", ".join("%s %d" % x for x in fin_bad.most_common(3)) or "-")))
        report["sets"].append({
            "corpus": label, "n": n, "rows_used": bool(rows),
            "raw_unsupported_cases": raw_cases, "raw_by_field": dict(raw_bad),
            "final_committed": fin_n, "final_unsupported_cases": fin_cases,
            "final_by_field": dict(fin_bad), "examples": examples,
        })

    print("-" * 82)
    tot_raw = sum(s["raw_unsupported_cases"] for s in report["sets"])
    tot_fin = sum(s["final_unsupported_cases"] for s in report["sets"])
    tot_com = sum(s["final_committed"] for s in report["sets"])
    print("합계: raw 기준 %d건에 근거 없는 critical field · 하네스 확정 %d건 중 %d건 잔존"
          % (tot_raw, tot_com, tot_fin))
    print()
    print("해석: 'raw 기준' 이 크고 '확정분 기준' 이 작을수록 하네스가 근거 없는 실행을 걸러낸 것이다.")
    print("      확정분에 남은 건은 완전성 게이트가 '값이 있는지' 만 보고 '근거가 있는지' 는")
    print("      보지 않아 통과한 경우다 — 알려진 한계이며 fail-closed 확장 후보다.")
    if report["sets"]:
        ex = [e for s in report["sets"] for e in s["examples"]][:5]
        if ex:
            print("\n확정분 잔존 예시:")
            for e in ex:
                print("  %-22s %-44s %s" % (e["id"], e["nl"], e["fields"]))

    report["total"] = {"raw_unsupported_cases": tot_raw,
                       "final_committed": tot_com, "final_unsupported_cases": tot_fin}
    if args.json:
        json.dump(report, open(args.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("\n→", args.json)


if __name__ == "__main__":
    main()
