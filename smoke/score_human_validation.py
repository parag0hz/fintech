#!/usr/bin/env python3
"""사람 라벨 채점 — 사람↔사람 일치도(Cohen's kappa)와 사람↔gold 일치도.

왜 kappa 인가: 단순 일치율(raw agreement)은 한쪽 답이 몰려 있으면 우연히 높게 나온다.
    예를 들어 90%가 BUY 인 셋에서는 둘 다 무조건 BUY 라고만 해도 90% 일치한다.
    kappa 는 우연 일치를 빼고 본다(κ<0.4 약함 / 0.4~0.6 보통 / 0.6~0.8 상당 / >0.8 거의 완전).

무엇을 답하나:
  1) 사람끼리 일치하는가 — 낮으면 **과제 정의가 모호**한 것이지 모델 문제가 아니다.
  2) 사람과 우리 gold 가 일치하는가 — 낮으면 **gold 가 틀렸을 수 있다**.
  3) 어디서 갈리는가 — 재판정(adjudication) 대상 목록.

표준 라이브러리만 사용. 실행: python3 score_human_validation.py
"""
import json, os, glob, sys, io
from collections import Counter, defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, "human_validation")
FIELDS = ("side", "condition", "abstain")


def load(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def norm(v):
    """빈 값은 None(미작성). 'true'/'false' 문자열과 bool 을 통일."""
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return "true" if v else "false"
    s = str(v).strip()
    low = s.lower()
    if low in ("true", "false"):
        return low
    return s.upper() if low in ("buy", "sell", "none", "le", "ge") else s


def kappa(pairs):
    """Cohen's kappa. pairs = [(a, b), ...] — 둘 다 값이 있는 것만."""
    n = len(pairs)
    if n == 0:
        return None
    po = sum(1 for a, b in pairs if a == b) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    labels = set(ca) | set(cb)
    pe = sum((ca[l] / n) * (cb[l] / n) for l in labels)
    if pe >= 1.0:
        return 1.0 if po >= 1.0 else 0.0
    return (po - pe) / (1 - pe)


def band(k):
    if k is None:
        return "-"
    return ("거의 완전" if k > .8 else "상당" if k > .6 else
            "보통" if k > .4 else "약함" if k > .2 else "거의 없음")


def main():
    if not os.path.isdir(DIR):
        print("!! %s 없음 — 먼저 build_human_validation_set.py 를 실행하세요." % DIR)
        return
    gold = {g["id"]: g for g in load(os.path.join(DIR, "_gold_DO_NOT_SHOW.jsonl"))} \
        if os.path.exists(os.path.join(DIR, "_gold_DO_NOT_SHOW.jsonl")) else {}

    anns = {}
    for p in sorted(glob.glob(os.path.join(DIR, "annotator_*.jsonl"))):
        name = os.path.basename(p)[len("annotator_"):-len(".jsonl")]
        rows = {r["id"]: r for r in load(p)}
        filled = sum(1 for r in rows.values() if any(norm(r.get(f)) for f in FIELDS))
        anns[name] = rows
        print("· annotator %-3s %3d건 중 %3d건 작성 (%.0f%%)" % (name, len(rows), filled,
                                                            100 * filled / max(len(rows), 1)))
    if not anns:
        print("!! annotator_*.jsonl 없음")
        return
    if all(sum(1 for r in rows.values() if any(norm(r.get(f)) for f in FIELDS)) == 0
           for rows in anns.values()):
        print("\n아직 아무도 라벨링하지 않았습니다. human_validation_guide.md 를 보고 채운 뒤 다시 실행하세요.")
        return

    names = sorted(anns)
    # 1) 사람 ↔ 사람
    print("\n" + "=" * 70)
    print("1. 사람끼리 일치도 (낮으면 과제 정의가 모호한 것)")
    print("=" * 70)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            print("\n  %s ↔ %s" % (a, b))
            for f in FIELDS:
                pairs = [(norm(anns[a][k].get(f)), norm(anns[b][k].get(f)))
                         for k in anns[a] if k in anns[b]
                         and norm(anns[a][k].get(f)) and norm(anns[b][k].get(f))]
                if not pairs:
                    print("    %-10s (미작성)" % f); continue
                raw = sum(1 for x, y in pairs if x == y) / len(pairs)
                k = kappa(pairs)
                print("    %-10s n=%-3d 일치 %5.1f%%  κ=%s (%s)" % (
                    f, len(pairs), 100 * raw,
                    ("%.3f" % k) if k is not None else "-", band(k)))
            # 3개 필드를 한꺼번에 맞혔는가 — 필드별 κ 가 높아도 joint 는 훨씬 낮을 수 있다.
            # 실제 주문은 세 필드가 동시에 맞아야 하므로 이쪽이 제품 관점의 일치도다.
            joint = [(tuple(norm(anns[a][k].get(f)) for f in FIELDS),
                      tuple(norm(anns[b][k].get(f)) for f in FIELDS))
                     for k in anns[a] if k in anns[b]
                     and all(norm(anns[a][k].get(f)) for f in FIELDS)
                     and all(norm(anns[b][k].get(f)) for f in FIELDS)]
            if joint:
                jr = sum(1 for x, y in joint if x == y) / len(joint)
                print("    %-10s n=%-3d 일치 %5.1f%%  (side·condition·abstain 3개 동시)"
                      % ("JOINT", len(joint), 100 * jr))

    # 2) 사람 ↔ gold
    if gold:
        print("\n" + "=" * 70)
        print("2. 사람 ↔ 우리 gold (낮으면 gold 가 틀렸을 수 있다)")
        print("=" * 70)
        for a in names:
            print("\n  annotator %s" % a)
            for f in FIELDS:
                pairs = []
                for k_, r in anns[a].items():
                    hv, g = norm(r.get(f)), gold.get(k_)
                    if hv and g:
                        pairs.append((hv, norm(g["gold"].get(f))))
                if not pairs:
                    print("    %-10s (미작성)" % f); continue
                raw = sum(1 for x, y in pairs if x == y) / len(pairs)
                kp = kappa(pairs)
                print("    %-10s n=%-3d 일치 %5.1f%%  κ=%s (%s)" % (
                    f, len(pairs), 100 * raw,
                    ("%.3f" % kp) if kp is not None else "-", band(kp)))
            jt = [(tuple(norm(anns[a][k_].get(f)) for f in FIELDS),
                   tuple(norm(gold[k_]["gold"].get(f)) for f in FIELDS))
                  for k_ in anns[a] if k_ in gold
                  and all(norm(anns[a][k_].get(f)) for f in FIELDS)]
            if jt:
                jr = sum(1 for x, y in jt if x == y) / len(jt)
                print("    %-10s n=%-3d 일치 %5.1f%%  (3개 동시 — 주문이 성립하려면 이게 맞아야 한다)"
                      % ("JOINT", len(jt), 100 * jr))

        # 3) 재판정 대상
        print("\n" + "=" * 70)
        print("3. 재판정 대상 — 사람(들)이 gold 와 다르게 본 케이스")
        print("=" * 70)
        dis = []
        for k_ in gold:
            g = {f: norm(gold[k_]["gold"].get(f)) for f in FIELDS}
            for a in names:
                r = anns[a].get(k_)
                if not r:
                    continue
                diff = {f: (norm(r.get(f)), g[f]) for f in FIELDS
                        if norm(r.get(f)) and norm(r.get(f)) != g[f]}
                if diff:
                    dis.append((k_, a, diff, gold[k_].get("src")))
        if not dis:
            print("  없음 — 사람과 gold 가 일치")
        else:
            byid = defaultdict(list)
            for k_, a, d, src in dis:
                byid[k_].append((a, d, src))
            print("  %d개 케이스에서 불일치 (사람 전원이 다르게 본 것부터)\n" % len(byid))
            for k_, lst in sorted(byid.items(), key=lambda x: -len(x[1])):
                mark = " ★ 전원 불일치 — gold 재검토 필요" if len(lst) == len(names) else ""
                print("  %-22s (%s)%s" % (k_, lst[0][2], mark))
                for a, d, _ in lst:
                    print("      %s: %s" % (a, ", ".join(
                        "%s 사람=%s / gold=%s" % (f, v[0], v[1]) for f, v in d.items())))
            out = os.path.join(DIR, "disagreements.json")
            json.dump([{"id": k_, "src": lst[0][2],
                        "annotators": [{"who": a, "diff": {f: {"human": v[0], "gold": v[1]}
                                                            for f, v in d.items()}} for a, d, _ in lst]}
                       for k_, lst in byid.items()],
                      open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print("\n  → %s 에 저장" % os.path.basename(out))

    # 4) 사람도 애매하다고 표시한 것
    amb = defaultdict(list)
    for a in names:
        for k_, r in anns[a].items():
            if norm(r.get("ambiguous")) == "true":
                amb[k_].append(a)
    if amb:
        print("\n" + "=" * 70)
        print("4. 사람이 '애매하다'고 표시한 케이스 %d건" % len(amb))
        print("=" * 70)
        print("  이런 케이스에서 하네스가 '확인 요청'을 하는 것은 과잉보류가 아니라 정상 동작이다.")
        for k_, who in sorted(amb.items(), key=lambda x: -len(x[1]))[:15]:
            print("    %-22s %s" % (k_, ",".join(who)))


if __name__ == "__main__":
    main()
