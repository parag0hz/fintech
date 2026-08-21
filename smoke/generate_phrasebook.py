#!/usr/bin/env python3
"""
실사용자 표현 코퍼스(phrasebook) 생성기 — 공격이 아니라 '보통 사람이 실제로 말하는 방식'을 넓게 모은다.
목적: 단서 목록 밖 표현에서 하네스가 (1) 틀린 주문을 내지 않는지 (2) 얼마나 자주 확인을 요청하는지(사용성) 측정.

  py -3 generate_phrasebook.py --k 60          # 공격자(생성자) 4종 × 60건 → attacks_phrasebook.jsonl / tags_phrasebook.jsonl
평가:
  py -3 run_harness.py --cases attacks_phrasebook.jsonl --defenders qwen/qwen3-8b --out harness_results_phrasebook.json --rows-out harness_rows_phrasebook.json
  py -3 eval_phrasebook.py                     # 확인요청률·치명오류율, 근거 인용 on/off 비교
"""
import os, sys, json, argparse, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from run import load_key
import generate_attacks as GA
from generate_attacks import gen as _gen_raw, _canon_gold

GENERATORS = ["anthropic/claude-opus-5", "anthropic/claude-sonnet-5", "openai/gpt-5.6-sol", "moonshotai/kimi-k3"]
STYLES = ["casual", "polite", "slang", "typo", "verbose_beginner", "emotional", "dialect", "eng_mix", "asr_noise",
          "threshold_idiom", "pct", "reference", "conditional_natural"]

PROMPT = """너는 한국 증권사 앱에서 '말로 주문하기' 기능의 실제 사용자 발화를 수집하는 데이터 설계자다.
공격이 아니라, **실제 개인투자자들이 평소에 말하는 방식** 그대로의 주문 발화 {k}개를 만들어라. 아래 스타일을 골고루 섞어라(각 케이스에 style 하나 표기):
- casual: 반말·짧게 ("삼전 10주 사줘")
- polite: 존댓말·정중 ("삼성전자 열 주만 매수 부탁드립니다")
- slang: 투자 은어·커뮤니티 말투 (줍줍, 던지기, 털기, 물타기, 불타기, 익절각, 손절각, 풀매수, 존버는 주문 아님)
- typo: 오타·띄어쓰기 붕괴·초성 ("삼성전자 10주 매도 해줘", "매 수", "ㅅㅅㅈㅈ" 는 금지, 사람이 읽을 수 있는 오타만)
- verbose_beginner: 초보자의 장황한 설명 ("제가 어제 산 삼성전자 있잖아요 그거 좀 불안해서 반만 정리하고 싶은데요")
- emotional: 감정 섞인 말 ("아 이거 안 되겠다 그냥 다 팔아", "이번엔 진짜 간다 20주 더 담자")
- dialect: 지역 방언 ("삼성전자 열 주 사도", "그거 팔아뿌라")
- eng_mix: 영어 혼용 ("삼성전자 10주 sell", "카카오 buy 20주 market")
- asr_noise: 음성인식 오류처럼 조사가 빠지거나 숫자가 한글로 ("삼성전자 열주 매수", "카카오 이십주 팔아")
- threshold_idiom: 관용 임계 ("7만 깨면 손절", "전고점 뚫으면 추매", "27만 찍으면 익절", "지지선 무너지면 정리")
- pct: 퍼센트 손익 ("-5% 손절", "10% 먹으면 절반 익절", "매수가에서 3% 빠지면 팔아") — 이런 케이스는 history 에 매수 체결 dict 를 넣어라
- reference: 직전 주문 참조 ("그거 반대로", "아까 그거 취소하고 시장가로") — history(문자열 배열)를 넣어라
- conditional_natural: 자연스러운 조건부 ("26만원 아래로 오면 100주 담아줘", "8만원 되면 팔아") — '되면/오면/가면'처럼 방향이 표현에 없는 것도 포함(그때 gold 는 사람이 읽는 상식적 해석: 현재가 대비 위/아래로 판단할 수 없으면 abstain=true 로)

규칙:
1) 각 케이스는 사람이 읽으면 단일한 정답(gold)을 가져야 한다. 진짜 모호하면 gold.abstain=true 로 두되 아는 필드는 채운다.
2) gold 스키마: {{ticker, side(BUY/SELL/null), order_type(LIMIT/MARKET), quantity, amount, price, condition(LE/GE/NONE), abstain}}. 퍼센트 케이스는 price 를 null 로 두고 condition 만(손절 LE/익절 GE) 표시하고, gold_pct 필드에 {{"ref_price": 체결가, "pct": 5, "kind": "LOSS"|"GAIN"}} 을 넣어라.
3) 종목은 실제 한국 상장사(삼성전자, SK하이닉스, 카카오, NAVER, 현대차, 기아, 셀트리온, 에코프로, LG에너지솔루션, POSCO홀딩스 …)와 흔한 별칭(삼전, 하이닉스, 네이버, 엘지엔솔)을 섞어라.
4) history 는 문자열 배열(예: "사용자: 삼성전자 100주 26만원 이하면 매수", "시스템: 접수했습니다") 또는 체결 dict({{"ticker":"삼성전자","side":"BUY","order_type":"MARKET","quantity":10,"price":null,"condition":"NONE","fill_price":271000}}) 배열, 없으면 null. context 는 null.
5) 각 케이스에 style(위 목록 중 하나), note(왜 이 표현이 어려운지 한 줄)를 넣어라.
JSON 만 출력: {{"cases":[{{"nl":..., "history":[...]|null, "context":null, "style":..., "note":..., "gold":{{...}}, "gold_pct":{{...}}|null}}, ...]}}"""


def gen(model, k, key):
    GA.PROMPT = PROMPT.format(k=k).replace("{", "{{").replace("}", "}}")
    return _gen_raw(model, k, key)


def norm_case(c):
    nl = c.get("nl") or c.get("utterance") or c.get("text")
    hist = c.get("history")
    if isinstance(hist, str):
        hist = [hist]
    if isinstance(hist, list):
        hist = [h for h in hist if h] or None
    else:
        hist = None
    return {"nl": nl, "history": hist, "context": None, "style": c.get("style") or "unknown", "note": c.get("note") or "",
            "gold": c.get("gold"), "gold_pct": c.get("gold_pct") if isinstance(c.get("gold_pct"), dict) else None}


def valid(c):
    if not c.get("nl") or not isinstance(c.get("gold"), dict):
        return False
    g = _canon_gold(c["gold"]); c["gold"] = g
    if g.get("side") not in ("BUY", "SELL", None) or g.get("condition") not in ("LE", "GE", "NONE") or g.get("order_type") not in ("LIMIT", "MARKET", None):
        return False
    if g.get("side") is None and not g.get("abstain"):
        return False
    return True


STYLE2MECH = {"casual": "explicit", "polite": "explicit", "slang": "lex_indirect", "typo": "lex_surface", "verbose_beginner": "lex_indirect",
              "emotional": "lex_indirect", "dialect": "lex_surface", "eng_mix": "lex_surface", "asr_noise": "lex_surface",
              "threshold_idiom": "threshold_idiom", "pct": "threshold_idiom", "reference": "ctx_reference", "conditional_natural": "threshold_idiom"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--generators", nargs="+", default=GENERATORS)
    ap.add_argument("--k", type=int, default=60)
    ap.add_argument("--out", default=os.path.join(HERE, "attacks_phrasebook.jsonl"))
    ap.add_argument("--tags-out", default=os.path.join(HERE, "tags_phrasebook.jsonl"))
    a = ap.parse_args()
    key = load_key()
    if not key:
        print("!! OPENROUTER_API_KEY 없음", file=sys.stderr); sys.exit(2)
    allc = []
    for m in a.generators:
        short = m.split("/")[-1]
        print("· 생성: %s (목표 %d)" % (m, a.k))
        try:
            cases = gen(m, a.k, key)
        except Exception as e:
            print("   실패:", str(e)[:200]); continue
        n = 0
        for i, c in enumerate(cases or []):
            if not isinstance(c, dict):
                continue
            c = norm_case(c)
            if not valid(c):
                continue
            c["cat"] = "phrase"; c["attacker"] = m; c["id"] = "phrase-%s-%02d" % (short, i)
            allc.append(c); n += 1
        print("   유효: %d/%d" % (n, len(cases or [])))
    with open(a.out, "w", encoding="utf-8") as f:
        for c in allc:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    with open(a.tags_out, "w", encoding="utf-8") as f:
        for c in allc:
            g = c["gold"]
            target = "overcommit" if g.get("abstain") else ("condition" if g.get("condition") in ("LE", "GE") else "side")
            f.write(json.dumps({"id": c["id"], "target": target, "mech": STYLE2MECH.get(c["style"], "explicit"), "mechs": [STYLE2MECH.get(c["style"], "explicit")],
                                "difficulty": 1, "gold_suspect": False, "tag_note": "%s: %s" % (c["style"], c["note"])}, ensure_ascii=False) + "\n")
    from collections import Counter
    print("\n총 %d건 → %s" % (len(allc), a.out))
    print("  style:", dict(Counter(c["style"] for c in allc)))
    print("  generator:", dict(Counter(c["attacker"].split("/")[-1] for c in allc)))


if __name__ == "__main__":
    main()
