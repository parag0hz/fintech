#!/usr/bin/env python3
"""adjudication.json 의 만장일치(3/3) 불일치 판정을 gold 에 반영한다(사람 확인 후 실행). 반영 이력은 케이스에 `gold_note` 로 남긴다.
  py -3 apply_adjudication.py                # 미리보기
  py -3 apply_adjudication.py --write --ids traj-01 deepseek-v4-pro-12
"""
import os, sys, json, argparse, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))

ap = argparse.ArgumentParser()
ap.add_argument("--write", action="store_true")
ap.add_argument("--ids", nargs="*", default=None, help="반영할 id (기본: 3/3 만장일치 불일치 전부)")
ap.add_argument("--note", default="gold adjudicated by 3-judge panel (gpt-5.6-sol/glm-5.2/kimi-k3, unanimous) 2026-08-18")
ap.add_argument("--file", default="adjudication.json")
a = ap.parse_args()

adj = json.load(open(os.path.join(HERE, a.file), encoding="utf-8"))
targets = {}
for r in adj:
    if not r["disagree"]:
        continue
    if a.ids is not None and r["id"] not in a.ids:
        continue
    unanimous = all(r["majority"][f]["votes"] == r["majority"][f]["n"] == 3 for f in r["disagree"])
    if a.ids is None and not unanimous:
        continue
    targets[r["id"]] = (r["file"], {f: r["majority"][f]["value"] for f in r["disagree"]})

for cid, (fn, ch) in targets.items():
    print("%-22s %s: %s" % (cid, fn, ch))
if not a.write:
    print("(미리보기. --write 로 반영)"); sys.exit(0)

files = {}
for cid, (fn, ch) in targets.items():
    files.setdefault(fn, {})[cid] = ch
for fn, chs in files.items():
    p = os.path.join(HERE, fn)
    lines = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    for c in lines:
        if c["id"] in chs:
            old = dict(c["gold"])
            c["gold"].update(chs[c["id"]])
            c["gold_note"] = a.note + " | was " + json.dumps({k: old[k] for k in chs[c["id"]]}, ensure_ascii=False)
    with open(p, "w", encoding="utf-8") as f:
        for c in lines:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    # 태그의 gold_suspect 해제
    stem = fn.replace("attacks_", "").replace(".jsonl", "")
    tp = os.path.join(HERE, "tags_%s.jsonl" % stem)
    if os.path.exists(tp):
        tags = [json.loads(l) for l in open(tp, encoding="utf-8") if l.strip()]
        for t in tags:
            if t["id"] in chs:
                t["gold_suspect"] = False
                t["tag_note"] = (t.get("tag_note") or "") + " [adjudicated: " + json.dumps(chs[t["id"]], ensure_ascii=False) + "]"
        with open(tp, "w", encoding="utf-8") as f:
            for t in tags:
                f.write(json.dumps(t, ensure_ascii=False) + "\n")
    print("→ 반영:", fn, list(chs))
