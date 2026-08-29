// smoke/ 의 코퍼스·태그·결과 파일을 web/data/ 로 복사한다 (배포 컨테이너가 ../smoke 에 의존하지 않도록).
// 사용: npm run sync-data   (SMOKE_DIR 환경변수로 원본 위치 지정, 기본 ../smoke)
// 대상: attacks.jsonl, attacks_frontier9.jsonl, attacks_adaptive*.jsonl, tags_*.jsonl, results_full/q25.json,
//       harness_results*/harness_rows*.json, asr_*.json, snapshots/*/ 의 같은 패턴 파일
import { copyFileSync, existsSync, mkdirSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SRC = path.resolve(ROOT, process.env.SMOKE_DIR || "../smoke");
const DST = path.join(ROOT, "data");
const PATTERNS = [
  /^attacks\.jsonl$/, /^attacks_frontier9\.jsonl$/, /^attacks_adaptive[^/]*\.jsonl$/,
  /^tags_[^/]+\.jsonl$/, /^results_full\.json$/, /^results_q25\.json$/,
  /^harness_results(_v1)?\.json$/, /^harness_rows(_v1)?\.json$/, /^asr_[^/]+\.json$/,
  // 온프레미스 4bit 실측 — 심사위원 첫 화면의 헤드라인 수치가 이 파일에서 나온다(하드코딩 금지)
  /^harness_ko_local_[^/]+\.json$/, /^harness_(adojo|irr|ko|self47|fr9)_v25\.json$/,
];
const want = (f) => PATTERNS.some((r) => r.test(f));

if (!existsSync(SRC)) {
  console.log(`[sync-data] 원본 디렉터리 없음: ${SRC} — 기존 data/ 를 그대로 사용합니다.`);
  process.exit(0);
}
let n = 0;
function syncDir(src, dst) {
  mkdirSync(dst, { recursive: true });
  for (const f of readdirSync(src)) {
    if (!want(f)) continue;
    copyFileSync(path.join(src, f), path.join(dst, f)); n++;
  }
}
syncDir(SRC, DST);
const snaps = path.join(SRC, "snapshots");
if (existsSync(snaps)) for (const v of readdirSync(snaps)) {
  const sd = path.join(snaps, v);
  if (statSync(sd).isDirectory()) syncDir(sd, path.join(DST, "snapshots", v));
}
console.log(`[sync-data] ${n}개 복사 → ${DST}`);
