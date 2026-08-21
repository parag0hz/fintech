#!/usr/bin/env python3
"""한국어 임계 셋 정밀 벤치마크: LE/GE · 경계포함 · 표현별로 방향 정확도를 쪼개서 본다."""
import json, os, sys, collections, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from run import load_key, call_openrouter, normalize
from harness import harness_parse

HERE=os.path.dirname(os.path.abspath(__file__))

def raw_parse(model, case, key, retries=3):
    for a in range(retries):
        try:
            raw,_=call_openrouter(model, case.get("context"), case["nl"], key)
            return normalize(raw), True
        except Exception:
            time.sleep(1.5*(a+1))
    return None, False

def har_parse(model, case, key, retries=3):
    for a in range(retries):
        f,fl,u=harness_parse(model, case, key)
        if not u.get("_err"): return f, True
        time.sleep(1.5*(a+1))
    return None, False

def main():
    model=sys.argv[1] if len(sys.argv)>1 else "qwen/qwen3-8b"
    cases=[json.loads(l) for l in open(f"{HERE}/attacks_ko_threshold.jsonl")]
    key=load_key()
    raw_parse(model, cases[0], key)   # 모드 캐시 워밍업
    res={}
    def work(c):
        rp,rok=raw_parse(model,c,key); hp,hok=har_parse(model,c,key)
        return c,rp,rok,hp,hok
    with ThreadPoolExecutor(max_workers=4) as ex:
        for f in as_completed([ex.submit(work,c) for c in cases]):
            c,rp,rok,hp,hok=f.result()
            res[c["id"]]=(c,rp,rok,hp,hok)
    print(f"모델 {model} · {len(cases)}건\n")
    def cond_of(p): return (p or {}).get("condition")
    def side_of(p): return (p or {}).get("side")
    # 전체
    for label,idx in (("raw",1),("harness",3)):
        ok=[v for v in res.values() if v[idx+1]]
        cw=sum(1 for v in ok if cond_of(v[idx])!=v[0]["gold"]["condition"])
        sw=sum(1 for v in ok if side_of(v[idx])!=v[0]["gold"]["side"])
        print(f"[{label:8s}] n={len(ok):3d}  조건(LE/GE) 오류 {cw:3d} ({100*cw/max(1,len(ok)):.0f}%)  "
              f"방향(매수/매도) 오류 {sw:2d} ({100*sw/max(1,len(ok)):.0f}%)")
    # LE/GE 별
    print("\n=== 조건별 오류율 (gold 기준) ===")
    print(f"{'gold':6s} {'n':>4s} {'raw오류':>8s} {'하네스오류':>10s}")
    for g in ("LE","GE"):
        sub=[v for v in res.values() if v[0]["gold"]["condition"]==g]
        r=[v for v in sub if v[2]]; h=[v for v in sub if v[4]]
        re_=sum(1 for v in r if cond_of(v[1])!=g); he=sum(1 for v in h if cond_of(v[3])!=g)
        print(f"{g:6s} {len(sub):4d} {re_:5d}({100*re_/max(1,len(r)):3.0f}%) {he:6d}({100*he/max(1,len(h)):3.0f}%)")
    # 경계 포함/배타
    print("\n=== 경계 포함(이상/이하) vs 배타(초과/미만) ===")
    for inc in (True,False):
        sub=[v for v in res.values() if v[0]["inclusive"]==inc]
        r=[v for v in sub if v[2]]; h=[v for v in sub if v[4]]
        re_=sum(1 for v in r if cond_of(v[1])!=v[0]["gold"]["condition"])
        he=sum(1 for v in h if cond_of(v[3])!=v[0]["gold"]["condition"])
        tag="포함(이상/이하)" if inc else "배타(초과/미만)"
        print(f"{tag:16s} n={len(sub):3d}  raw {re_:2d}({100*re_/max(1,len(r)):3.0f}%)  하네스 {he:2d}({100*he/max(1,len(h)):3.0f}%)")
    # 표현별 최악
    print("\n=== 표현별 raw 조건오류 (상위) ===")
    per=collections.defaultdict(lambda:[0,0])
    for c,rp,rok,hp,hok in res.values():
        if not rok: continue
        per[c["expr_ko"]][1]+=1
        if cond_of(rp)!=c["gold"]["condition"]: per[c["expr_ko"]][0]+=1
    for k,(b,n) in sorted(per.items(),key=lambda x:-x[1][0]/max(1,x[1][1]))[:10]:
        if b: print(f"  {k:<14} {b}/{n} ({100*b/n:.0f}%)")
    json.dump({k:{"gold":v[0]["gold"],"nl":v[0]["nl"],"expr":v[0]["expr_ko"],
                  "raw":v[1],"harness":v[3]} for k,v in res.items()},
              open(f"{HERE}/ko_threshold_detail_{model.split('/')[-1]}.json","w"),
              ensure_ascii=False, indent=2)
    print(f"\n상세 → ko_threshold_detail_{model.split('/')[-1]}.json")

if __name__=="__main__": main()
