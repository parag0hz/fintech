#!/usr/bin/env python3
"""
BULL(中/英 병렬) 방향성 표현 → 한국어 임계 표현 뱅크 + 균형 잡힌 주문 테스트셋 생성.

배경: BULL은 방향성 비교 1,291건 중 >:< = 5.4:1, >=:<= = 7:1 로 심하게 편중.
     한국어는 이상/초과/이하/미만을 법령 수준에서 구분하므로(영어 'more than'보다 정밀)
     LE/GE 경계를 훨씬 정확히 시험할 수 있다. → 균형 잡힌 한국어 셋을 우리가 만든다.
"""
import json, random, collections, os, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
BULL = "/Users/limdong-won/Downloads/BULL"

# ── 1) BULL 중국어 방향어 → 한국어 대응 (한자어 공유로 1:1에 가까움) ──────────
# op: SQL 연산자 / incl: 경계 포함 여부 / ko: 한국어 표현들
CN_TO_KO = [
    # 포함(≥, ≤) — 법령·금융 문서에서 쓰는 정확한 표현
    ("以上",   ">=", True,  ["이상", "이상이면", "이상으로 올라가면"]),
    ("不低于", ">=", True,  ["이상", "밑돌지 않으면", "아래로 안 내려가면"]),
    ("不少于", ">=", True,  ["이상", "최소"]),
    ("以下",   "<=", True,  ["이하", "이하면", "이하로 내려오면"]),
    ("不超过", "<=", True,  ["이하", "넘지 않으면", "초과하지 않으면"]),
    ("不高于", "<=", True,  ["이하", "위로 안 올라가면"]),
    # 배타(>, <)
    ("超过",   ">",  False, ["초과", "초과하면", "넘으면", "넘어서면", "돌파하면", "위로 뚫으면"]),
    ("大于",   ">",  False, ["초과", "보다 크면", "보다 높으면"]),
    ("高于",   ">",  False, ["보다 높으면", "위로 올라가면", "상회하면"]),
    ("小于",   "<",  False, ["미만", "미만이면", "보다 작으면"]),
    ("低于",   "<",  False, ["보다 낮으면", "아래로 떨어지면", "하회하면", "밑으로 내려가면", "밑돌면"]),
]

def build_bank():
    """BULL 실제 등장 빈도로 가중한 한국어 임계 표현 뱅크."""
    cn = json.load(open(f"{BULL}/BULL-cn/train.json")) + json.load(open(f"{BULL}/BULL-cn/dev.json"))
    freq = collections.Counter()
    for r in cn:
        for kw, _, _, _ in CN_TO_KO:
            if kw in r["question"]:
                freq[kw] += 1
    bank = {"GE": [], "LE": []}
    for kw, op, incl, kos in CN_TO_KO:
        slot = "GE" if op in (">", ">=") else "LE"
        for ko in kos:
            bank[slot].append({
                "ko": ko, "op": op, "inclusive": incl,
                "src_cn": kw, "bull_freq": freq.get(kw, 0),
                # 우리 스키마 라벨: 경계 포함 여부와 무관하게 방향만 본다
                "condition": "GE" if op in (">", ">=") else "LE",
            })
    return bank, freq

# ── 2) 균형 잡힌 한국어 주문 케이스 생성 ────────────────────────────────
TICKERS = ["삼성전자", "SK하이닉스", "NAVER", "카카오", "현대차", "기아",
           "셀트리온", "POSCO홀딩스", "LG에너지솔루션", "삼성SDI", "에코프로", "한화에어로스페이스"]
PRICES  = [26000, 41500, 52000, 68000, 90000, 124000, 178000, 240000, 305000, 412000]
QTYS    = [5, 10, 20, 30, 50, 100, 200, 300]
BUY     = ["매수", "사줘", "담아", "매수 걸어줘", "매수 주문 넣어줘"]
SELL    = ["매도", "팔아", "정리해", "매도 걸어줘", "매도 주문 넣어줘"]

def won(p):
    """26000 -> '2만6천원' 같은 자연스러운 한국어 표기도 섞는다."""
    if p % 10000 == 0: return f"{p//10000}만원"
    man, rest = divmod(p, 10000)
    if rest % 1000 == 0: return f"{man}만{rest//1000}천원"
    return f"{p:,}원"

def gen_cases(bank, n_per_cell=12, seed=7):
    rnd = random.Random(seed)
    cases = []
    cid = 0
    # 4개 셀: (조건 LE/GE) × (방향 BUY/SELL) — 균형 강제
    for cond in ("LE", "GE"):
        for side in ("BUY", "SELL"):
            for _ in range(n_per_cell):
                expr = rnd.choice(bank[cond])
                tk = rnd.choice(TICKERS); pr = rnd.choice(PRICES); qt = rnd.choice(QTYS)
                verb = rnd.choice(BUY if side == "BUY" else SELL)
                ko = expr["ko"]
                # 표현 형태에 맞춰 자연스러운 문장 구성
                if ko in ("이상", "이하", "초과", "미만", "최소"):
                    stem = f"{tk} {won(pr)} {ko}"
                elif ko.startswith("보다"):
                    stem = f"{tk} {won(pr)}{ko}"
                else:
                    stem = f"{tk} {won(pr)} {ko}"
                nl = f"{stem} {qt}주 {verb}"
                cases.append({
                    "id": f"kothr-{cid:03d}", "cat": "threshold", "attacker": "bull-derived",
                    "nl": nl, "context": None,
                    "expr_ko": ko, "expr_src_cn": expr["src_cn"],
                    "inclusive": expr["inclusive"], "sql_op": expr["op"],
                    "gold": {"ticker": tk, "side": side, "order_type": "LIMIT",
                             "quantity": qt, "amount": None, "price": pr,
                             "condition": cond, "abstain": False},
                })
                cid += 1
    rnd.shuffle(cases)
    return cases

# ── 3) 최소쌍(minimal pair): 한 슬롯만 뒤집기 (Dr.Spider 레시피) ─────────
def gen_minimal_pairs(cases, bank, seed=11):
    """같은 문장에서 임계 표현만 반대 방향으로 바꾼 쌍 → 방향 민감도 정밀 측정."""
    rnd = random.Random(seed)
    pairs = []
    for c in cases[:40]:
        opp = "GE" if c["gold"]["condition"] == "LE" else "LE"
        alt = rnd.choice([e for e in bank[opp] if e["inclusive"] == c["inclusive"]] or bank[opp])
        nl2 = c["nl"].replace(c["expr_ko"], alt["ko"], 1)
        if nl2 == c["nl"]:
            continue
        g2 = dict(c["gold"]); g2["condition"] = opp
        pairs.append({
            "id": c["id"] + "-flip", "cat": "threshold_minimal_pair", "attacker": "bull-derived",
            "nl": nl2, "context": None, "pair_of": c["id"],
            "expr_ko": alt["ko"], "expr_src_cn": alt["src_cn"],
            "inclusive": alt["inclusive"], "sql_op": alt["op"], "gold": g2,
        })
    return pairs

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=12); a = ap.parse_args()
    bank, freq = build_bank()
    print("=== BULL 중국어 방향어 실제 등장 빈도 ===")
    for kw, n in freq.most_common():
        ko = next(x[3][0] for x in CN_TO_KO if x[0] == kw)
        print(f"  {kw:<6} {n:>4}회  → 한국어 '{ko}'")
    json.dump(bank, open(f"{HERE}/ko_threshold_bank.json", "w"), ensure_ascii=False, indent=2)
    print(f"\n뱅크: GE {len(bank['GE'])}개 표현 · LE {len(bank['LE'])}개 표현 → ko_threshold_bank.json")

    cases = gen_cases(bank, a.n)
    pairs = gen_minimal_pairs(cases, bank)
    allc = cases + pairs
    with open(f"{HERE}/attacks_ko_threshold.jsonl", "w") as f:
        for c in allc: f.write(json.dumps(c, ensure_ascii=False) + "\n")
    d = collections.Counter((c["gold"]["condition"], c["gold"]["side"]) for c in allc)
    print(f"\n생성: 기본 {len(cases)}건 + 최소쌍 {len(pairs)}건 = {len(allc)}건 → attacks_ko_threshold.jsonl")
    print("  균형:", dict(d))
    print("\n=== 샘플 ===")
    for c in allc[:6]:
        print(f"  [{c['gold']['condition']}/{c['gold']['side']}] {c['nl']}")
        print(f"     (中 {c['expr_src_cn']} → 韓 '{c['expr_ko']}', SQL {c['sql_op']}, 경계포함={c['inclusive']})")
