#!/usr/bin/env python3
"""사람 검증용 독립 평가 세트 생성 — gold 를 숨긴 블라인드 라벨링 템플릿.

왜: 이 프로젝트의 가장 큰 평가 리스크는 "공격도 정답도 채점도 본인이 했다"이다.
    핵심 코퍼스 189건 중 제3자 모델 패널 판정은 12건(6%)뿐이고 사람 라벨은 0건이다.
    모델 패널조차 판정자 프롬프트가 해석을 미리 지시해 독립 검증으로 보기 어렵다.

무엇을: 기존 코퍼스에서 층화 추출한 N건을 **gold 없이** 내보낸다. 사람은 발화만 보고
    독립적으로 라벨링하고, score_human_validation.py 가 gold 및 다른 사람과 대조한다.

원칙:
  - gold 를 템플릿에 넣지 않는다(앵커링 방지). 정답 파일은 별도 보관.
  - 사람 라벨을 코드로 생성하지 않는다. 빈 칸만 준다.
  - 표본은 층화 추출한다 — 쉬운 것만 뽑으면 일치율이 부풀려진다.

실행:
  python3 build_human_validation_set.py            # 기본 60건, 2인분 템플릿
  python3 build_human_validation_set.py --n 100 --annotators a b c
"""
import argparse, json, os, random
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
# 층화 축: 이 대역들이 골고루 들어가야 일치율이 의미를 갖는다
SOURCES = [
    ("attacks.jsonl", "tags_attacks.jsonl"),
    ("attacks_frontier9.jsonl", "tags_frontier9.jsonl"),
    ("attacks_ko_threshold.jsonl", None),
    ("attacks_phrasebook.jsonl", "tags_phrasebook.jsonl"),
    ("attacks_agentdojo_ko.jsonl", "tags_agentdojo_ko.jsonl"),
    ("attacks_irrelevance_ko.jsonl", "tags_irrelevance_ko.jsonl"),
]


def load(fn):
    p = os.path.join(HERE, fn)
    if not os.path.exists(p):
        return []
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60, help="추출할 케이스 수")
    ap.add_argument("--annotators", nargs="+", default=["a", "b"])
    ap.add_argument("--seed", type=int, default=20260827)
    ap.add_argument("--out-dir", default=os.path.join(HERE, "human_validation"))
    args = ap.parse_args()
    rnd = random.Random(args.seed)

    # 1) 수집 + 태그 결합
    pool = []
    for cf, tf in SOURCES:
        cases = load(cf)
        tags = {t["id"]: t for t in load(tf)} if tf else {}
        for c in cases:
            if not c.get("nl"):
                continue
            t = tags.get(c.get("id"), {})
            pool.append({
                "id": c["id"], "src": cf, "nl": c["nl"],
                "history": c.get("history"), "context": c.get("context"),
                "gold": c["gold"],
                "stratum": "%s/%s" % (t.get("target") or c.get("cat") or "?",
                                      "abstain" if c["gold"].get("abstain") else "commit"),
            })

    # 2) 층화 추출 — 대역별로 고르게(쉬운 것만 뽑으면 일치율이 부풀려진다)
    by = defaultdict(list)
    for c in pool:
        by[c["stratum"]].append(c)
    strata = sorted(by)
    picked, i = [], 0
    while len(picked) < min(args.n, len(pool)):
        s = strata[i % len(strata)]
        if by[s]:
            picked.append(by[s].pop(rnd.randrange(len(by[s]))))
        elif all(not by[x] for x in strata):
            break
        i += 1
    rnd.shuffle(picked)   # 출처 순서로 정답을 유추하지 못하게

    os.makedirs(args.out_dir, exist_ok=True)

    # 3) 정답 파일(채점용) — 라벨러에게 주지 않는다
    with open(os.path.join(args.out_dir, "_gold_DO_NOT_SHOW.jsonl"), "w", encoding="utf-8") as f:
        for c in picked:
            f.write(json.dumps({"id": c["id"], "src": c["src"], "gold": c["gold"],
                                "stratum": c["stratum"]}, ensure_ascii=False) + "\n")

    # 4) 사람이 채울 빈 템플릿 — gold 없음
    for a in args.annotators:
        p = os.path.join(args.out_dir, "annotator_%s.jsonl" % a)
        if os.path.exists(p):
            print("  건너뜀(이미 있음, 덮어쓰지 않음):", os.path.basename(p))
            continue
        with open(p, "w", encoding="utf-8") as f:
            for c in picked:
                f.write(json.dumps({
                    "id": c["id"],
                    "nl": c["nl"],
                    "history": c["history"],
                    "context": c["context"],
                    # ↓ 여기부터 사람이 채운다 (빈 값 = 미작성)
                    "side": "",           # BUY / SELL / NONE
                    "condition": "",      # LE(이하) / GE(이상) / NONE
                    "abstain": "",        # true(확정 불가·되물어야 함) / false(확정 가능)
                    "ambiguous": "",      # true / false — 사람이 봐도 애매한가
                    "note": "",
                }, ensure_ascii=False) + "\n")
        print("  생성:", os.path.basename(p))

    print("\n%d건 추출 (층 %d개), 출력 → %s" % (len(picked), len(strata), args.out_dir))
    print("층 분포:", dict(sorted(
        ((s, sum(1 for c in picked if c["stratum"] == s)) for s in {c["stratum"] for c in picked}),
        key=lambda x: -x[1])))
    print("\n다음: human_validation_guide.md 를 읽고 annotator_*.jsonl 을 채운 뒤")
    print("      python3 score_human_validation.py")


if __name__ == "__main__":
    main()
