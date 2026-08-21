#!/usr/bin/env python3
"""
구 코퍼스 → 하네스 v2 케이스 스키마 마이그레이션.

v1은 context 문자열 안의 "직전 대화:" 마커로 신뢰 여부를 추정했다(결함). v2는 `history`(신뢰) / `context`(비신뢰)
필드를 구조적으로 분리한다. 이 스크립트는 오프라인·1회성으로, 사람이 만든 코퍼스에 한해 마커/카테고리/태그를
근거로 context 를 history 로 옮긴다. 런타임 하네스는 절대 이 추정을 하지 않는다.

이동 규칙(하나라도 해당하면 history 로):
  - context 가 신뢰 마커("직전 대화", "이전 대화", "대화 이력", "이전 턴", "직전 턴")로 시작
  - cat == "trajectory"
  - 태그 파일이 주어졌고 해당 id 의 mechs 에 ctx_reference / ctx_conflict 가 있음
단, context 에 인젝션 냄새(무시하|지시|명령|system|instruction|매도하라|전환)가 있으면 옮기지 않고 경고만 낸다.

사용: py -3 migrate_history.py attacks.jsonl [--tags tags_attacks.jsonl] [--write]
"""
import os, sys, json, re, argparse

MARK = re.compile(r"^\s*(직전 대화|이전 대화|대화 이력|이전 턴|직전 턴)\s*[:：\-–]?\s*", re.M)
INJ = re.compile(r"무시하|지시|명령|system|instruction|매도하라|전환하|바꿔라|override", re.I)
# 이력 텍스트 안에 끼워진 외부 블록("[뉴스 알림: …]") → 비신뢰 context 로 분리
EMBED = re.compile(r"\[(?:뉴스|알림|공시|리서치|속보|시스템|공지|메모)[^\]]*\]")


def load_jsonl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--tags", default=None)
    ap.add_argument("--write", action="store_true", help="실제로 파일을 덮어쓴다(기본은 미리보기)")
    a = ap.parse_args()

    cases = load_jsonl(a.path)
    tags = {}
    if a.tags and os.path.exists(a.tags):
        tags = {t["id"]: t for t in load_jsonl(a.tags)}

    moved, warned, split = [], [], []
    for c in cases:
        if "history" in c:
            # 2차 정리: 이력 안에 끼워진 외부 블록은 비신뢰 context 로 분리
            h = c.get("history")
            if isinstance(h, str) and EMBED.search(h) and not c.get("context"):
                blocks = EMBED.findall(h)
                c["context"] = "\n".join(blocks)
                c["history"] = EMBED.sub("", h).strip()
                split.append((c["id"], blocks[0][:50]))
            continue
        ctx = c.get("context")
        if not ctx or not isinstance(ctx, str) or not ctx.strip():
            continue
        by_marker = bool(MARK.match(ctx))
        by_cat = c.get("cat") == "trajectory"
        mechs = set(tags.get(c.get("id"), {}).get("mechs", []))
        by_tag = bool(mechs & {"ctx_reference", "ctx_conflict"})
        if not (by_marker or by_cat or by_tag):
            continue
        if INJ.search(ctx) and not by_marker:
            warned.append((c["id"], ctx[:60]))
            continue
        h = MARK.sub("", ctx).strip()
        c["context"] = None
        if EMBED.search(h):
            blocks = EMBED.findall(h)
            c["context"] = "\n".join(blocks)
            h = EMBED.sub("", h).strip()
            split.append((c["id"], blocks[0][:50]))
        c["history"] = h
        moved.append((c["id"], "marker" if by_marker else ("cat" if by_cat else "tag")))

    print("이동 %d건:" % len(moved))
    for i, why in moved:
        print("  %-22s (%s)" % (i, why))
    if split:
        print("이력 안 외부 블록 → context 분리 %d건:" % len(split))
        for i, s in split:
            print("  %-22s %s" % (i, s))
    if warned:
        print("경고(인젝션 냄새라 미이동, 확인 필요) %d건:" % len(warned))
        for i, s in warned:
            print("  %-22s %s" % (i, s))
    if a.write:
        with open(a.path, "w", encoding="utf-8") as f:
            for c in cases:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
        print("→ 저장:", a.path)
    else:
        print("(미리보기. 적용하려면 --write)")


if __name__ == "__main__":
    main()
