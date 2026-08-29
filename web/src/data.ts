/**
 * smoke/ 산출물(코퍼스·태그·결과) 로더 + 대시보드용 집계.
 * 파일은 SMOKE_DIR → ./data 순으로 찾고, 없으면 null(UI 는 '데이터 없음' 표시). mtime 기준 캐시.
 * 코퍼스: attacks.jsonl(자체작성) · attacks_frontier9.jsonl(프론티어) · attacks_adaptive*.jsonl(적응형 그룹).
 * 결과: harness_results[_v1].json / harness_rows[_v1].json (실험2), asr_<stem>[_v1].json / asr_rows_<stem>[_v1].json (ASR),
 *       snapshots/v2.0/*.json (패치 전 집계 = "v2.0" 열), 레거시 asr_8b/asr_32b.json.
 */
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
export const WEB_ROOT = path.resolve(HERE, "..");
const SNAPSHOT_DIRS: Array<{ sub: string; version: string }> = [{ sub: "snapshots/v2.0", version: "v2.0" }];

function dataDirs(): string[] {
  return [path.resolve(WEB_ROOT, process.env.SMOKE_DIR || "../smoke"), path.resolve(WEB_ROOT, "data")];
}

/** 대시보드/코퍼스가 읽는 파일 패턴 (sync-data 도 같은 규칙) */
export const DATA_PATTERNS: RegExp[] = [
  /^attacks\.jsonl$/, /^attacks_frontier9\.jsonl$/, /^attacks_adaptive[^/]*\.jsonl$/,
  /^tags_[^/]+\.jsonl$/, /^results_full\.json$/, /^results_q25\.json$/,
  /^harness_results(_v1)?\.json$/, /^harness_rows(_v1)?\.json$/,
  /^asr_[^/]+\.json$/,
];
export const isDataFile = (name: string) => DATA_PATTERNS.some((r) => r.test(name));

interface CacheEntry { mtime: number; size: number; value: unknown; path: string }
const cache = new Map<string, CacheEntry>();

export function locate(name: string): string | null {
  for (const d of dataDirs()) {
    const p = path.join(d, name);
    if (existsSync(p)) return p;
  }
  return null;
}

/** 데이터 디렉터리(들)에 있는 파일 이름 합집합 (스냅샷은 "snapshots/v2.0/x.json" 형태) */
export function listFiles(): string[] {
  const out = new Set<string>();
  for (const d of dataDirs()) {
    if (!existsSync(d)) continue;
    for (const f of readdirSync(d)) if (isDataFile(f)) out.add(f);
    for (const s of SNAPSHOT_DIRS) {
      const sd = path.join(d, s.sub);
      if (existsSync(sd)) for (const f of readdirSync(sd)) if (isDataFile(f)) out.add(`${s.sub}/${f}`);
    }
  }
  return [...out].sort();
}

function loadFile<T>(name: string, parse: (txt: string) => T): T | null {
  const p = locate(name);
  if (!p) { cache.delete(name); return null; }
  let st;
  try { st = statSync(p); } catch { return null; }
  const c = cache.get(name);
  if (c && c.path === p && c.mtime === st.mtimeMs && c.size === st.size) return c.value as T;
  try {
    const value = parse(readFileSync(p, "utf-8"));
    cache.set(name, { mtime: st.mtimeMs, size: st.size, value, path: p });
    return value;
  } catch (e) {
    console.warn(`[data] ${name} 파싱 실패: ${(e as Error).message}`);
    return null;
  }
}
export const loadJson = <T = unknown>(name: string): T | null => loadFile<T>(name, (t) => JSON.parse(t) as T);
export const loadJsonl = <T = unknown>(name: string): T[] | null =>
  loadFile<T[]>(name, (t) => t.split(/\r?\n/).filter((l) => l.trim()).map((l) => JSON.parse(l) as T));

// ── 코퍼스 ────────────────────────────────────────────────────────────────
export type CorpusKey = "attacks" | "frontier9" | "adaptive";
export const CORPUS_LABEL: Record<CorpusKey, string> = { attacks: "자체작성", frontier9: "프론티어", adaptive: "적응형" };

/** stem("", "frontier9", "adaptive", "adaptive2"…) → 코퍼스 그룹 */
export function stemGroup(stem: string): CorpusKey | null {
  if (stem === "" || stem === "attacks") return "attacks";
  if (stem === "frontier9") return "frontier9";
  if (stem.startsWith("adaptive")) return "adaptive";
  return null;
}
const stemOf = (file: string) => file === "attacks.jsonl" ? "" : file.replace(/^attacks_/, "").replace(/\.jsonl$/, "");
const casesFile = (stem: string) => stem ? `attacks_${stem}.jsonl` : "attacks.jsonl";
const tagsFile = (stem: string) => stem ? `tags_${stem}.jsonl` : "tags_attacks.jsonl";

/** 그룹별 stem 목록 (존재하는 파일 기준) */
export function corpusStems(): Record<CorpusKey, string[]> {
  const out: Record<CorpusKey, string[]> = { attacks: [], frontier9: [], adaptive: [] };
  for (const f of listFiles()) {
    if (!/^attacks(_[^/]+)?\.jsonl$/.test(f)) continue;
    const stem = stemOf(f), g = stemGroup(stem);
    if (g) out[g].push(stem);
  }
  return out;
}

export interface Gold { ticker: unknown; side: unknown; order_type: unknown; quantity: unknown; amount: unknown; price: unknown; condition: unknown; abstain: unknown }
export interface Tag { id: string; target?: string; mech?: string; mechs?: string[]; difficulty?: number; gold_suspect?: boolean; tag_note?: string }
export interface Case {
  id: string; cat?: string; nl: string; gold: Gold; history?: unknown; context?: string | null;
  attacker?: string; attack_note?: string; target?: string; mech?: string; mechs?: string[]; difficulty?: number; [k: string]: unknown;
}
export interface CaseWithTags extends Case { file: CorpusKey; stem: string; tags: Tag | null }

function tagMap(stem: string): Map<string, Tag> {
  return new Map((loadJsonl<Tag>(tagsFile(stem)) || []).map((t) => [t.id, t]));
}
/** 태그 파일에 없으면 케이스 자체의 target/mech/mechs/difficulty 필드(적응형 코퍼스)로 대체 */
function tagOf(c: Case, tags: Map<string, Tag>): Tag | null {
  const t = tags.get(c.id);
  if (t) return t;
  if (c.target || c.mech) return { id: c.id, target: c.target, mech: c.mech, mechs: c.mechs, difficulty: c.difficulty, gold_suspect: !!c.gold_suspect, tag_note: (c.tag_note as string) || c.attack_note };
  return null;
}

export function loadCorpus(key: CorpusKey): CaseWithTags[] | null {
  const stems = corpusStems()[key];
  if (!stems.length) return null;
  const out: CaseWithTags[] = [];
  for (const stem of stems) {
    const cases = loadJsonl<Case>(casesFile(stem));
    if (!cases) continue;
    const tags = tagMap(stem);
    for (const c of cases) out.push({ ...c, file: key, stem: stem || "attacks", tags: tagOf(c, tags) });
  }
  return out;
}

export function corpusCounts(): Record<CorpusKey, number | null> {
  const out = {} as Record<CorpusKey, number | null>;
  for (const k of Object.keys(CORPUS_LABEL) as CorpusKey[]) { const c = loadCorpus(k); out[k] = c ? c.length : null; }
  return out;
}

export function findCase(id: string): CaseWithTags | null {
  for (const k of Object.keys(CORPUS_LABEL) as CorpusKey[]) {
    const hit = loadCorpus(k)?.find((c) => c.id === id);
    if (hit) return hit;
  }
  return null;
}

// ── 결과 파일 ─────────────────────────────────────────────────────────────
export interface Score { critical: boolean; unnec_abstain?: boolean; ok_commit?: boolean; exact?: boolean; field_hits?: number; n_fields?: number; abstain_ok?: boolean }
export interface HRow {
  id: string; cat?: string; attacker?: string; gold: Gold;
  raw_pred: unknown; raw_err?: string | null; raw_score: Score | null;
  h_parsed?: unknown; h_final: unknown; h_flags: string[] | null; h_err?: string | null; h_score: Score | null;
  h_detail?: unknown; h_mode?: string;
}
interface RowsFile { rows: Record<string, HRow[]>; harness?: string; attacks?: string }
interface Exp1Row { id: string; cat?: string; err: string | null; pred: unknown; gold: Gold; score: Score; ms?: number; mode?: string; tok?: number }
interface Exp1File { cases?: number; summaries: Exp1Summary[]; rows: Record<string, Exp1Row[]> }
export interface Exp1Summary { model: string; n: number; exact: number; crit: number; err: number; field_acc: number; p50ms: number; cats: Record<string, [number, number]> }
type ByCat = Record<string, [number, number]>;
interface HarnessResultsEntry {
  raw_crit: number; raw_unnec: number; h_crit: number; h_unnec: number; raw_err?: number; h_err?: number;
  raw_bycat: ByCat; h_bycat: ByCat; flags: Record<string, number>;
  h_mech_target?: Record<string, Record<string, [number, number]>>; harness?: string; n?: number;
}
type Heat = Record<string, Record<string, [number, number]>>;
interface AsrFile {
  cells: Record<string, [number, number, number]>; errors?: Record<string, number>;
  heat_mech_target?: Record<string, Heat>; harness?: string; attacks?: string; defenders?: string[];
}

export interface ResultSource {
  key: string; kind: "exp2" | "asr"; version: string; corpus: CorpusKey; stem: string;
  label: string; agg: string; rows: string | null;
}

/** 존재하는 파일에서 결과 소스(집계+행) 목록을 만든다 */
export function resultSources(): ResultSource[] {
  const files = new Set(listFiles());
  const out: ResultSource[] = [];
  const has = (f: string) => files.has(f);
  const versionOf = (v1: boolean, snap: string | null) => snap ?? (v1 ? "v1" : "v2");
  const stemLabel = (stem: string) => stem === "" || stem === "attacks" ? "자체작성" : stem === "frontier9" ? "프론티어" : `적응형 ${stem === "adaptive" ? "" : stem.replace("adaptive", "#")}`.trim();
  for (const f of files) {
    const m = /^(?:(snapshots\/[^/]+)\/)?(harness_results|asr_(?!rows_)([^/]+?))(_v1)?\.json$/.exec(f);
    if (!m) continue;
    const snapDir = m[1] || null;
    const snapVer = snapDir ? SNAPSHOT_DIRS.find((s) => s.sub === snapDir)?.version ?? snapDir : null;
    const v1 = !!m[4];
    if (snapDir && v1) continue;                       // 스냅샷의 _v1 은 현재 v1 파일과 같은 내용 → 중복 제외
    const version = versionOf(v1, snapVer);
    if (m[2] === "harness_results") {
      const rows = !snapDir && has(`harness_rows${v1 ? "_v1" : ""}.json`) ? `harness_rows${v1 ? "_v1" : ""}.json` : null;
      out.push({ key: `exp2|${version}`, kind: "exp2", version, corpus: "attacks", stem: "attacks", label: `실험2 (자체작성) · 하네스 ${version}`, agg: f, rows });
    } else {
      const stem = m[3];
      const group = stemGroup(stem);
      if (!group || !has(casesFile(stem))) continue;      // asr_8b/asr_32b/asr_matrix 등 레거시는 별도 처리
      const rows = !snapDir && has(`asr_rows_${stem}${v1 ? "_v1" : ""}.json`) ? `asr_rows_${stem}${v1 ? "_v1" : ""}.json` : null;
      out.push({ key: `asr_${stem}|${version}`, kind: "asr", version, corpus: group, stem, label: `ASR (${stemLabel(stem)}) · 하네스 ${version}`, agg: f, rows });
    }
  }
  const vord = (v: string) => (v === "v1" ? 0 : v === "v2" ? 9 : 5);
  return out.sort((a, b) => a.kind.localeCompare(b.kind) || a.stem.localeCompare(b.stem) || vord(a.version) - vord(b.version));
}

export interface CaseOutcome {
  source: string; label: string; version: string; defender: string; mode: "exp1" | "harness";
  raw_pred?: unknown; raw_score?: Score | null; raw_err?: string | null;
  h_parsed?: unknown; h_final?: unknown; h_flags?: string[] | null; h_score?: Score | null; h_err?: string | null; h_detail?: unknown;
  pred?: unknown; score?: Score | null; err?: string | null;
}

/** 케이스 id 로 모든 결과 파일에서 방어자별 결과를 모은다 */
export function caseOutcomes(id: string): CaseOutcome[] {
  const out: CaseOutcome[] = [];
  for (const file of ["results_full.json", "results_q25.json"]) {
    const d = loadJson<Exp1File>(file);
    if (!d?.rows) continue;
    for (const [model, rows] of Object.entries(d.rows)) {
      const r = rows.find((x) => x.id === id);
      if (r) out.push({ source: file, label: "실험1 raw", version: "-", defender: model, mode: "exp1", pred: r.pred, score: r.score, err: r.err });
    }
  }
  for (const s of resultSources()) {
    if (!s.rows) continue;
    const d = loadJson<RowsFile>(s.rows);
    if (!d?.rows) continue;
    for (const [model, rows] of Object.entries(d.rows)) {
      const r = rows.find((x) => x.id === id);
      if (r) out.push({
        source: s.rows, label: s.label, version: s.version, defender: model, mode: "harness",
        raw_pred: r.raw_pred, raw_score: r.raw_score, raw_err: r.raw_err ?? null,
        h_parsed: r.h_parsed, h_final: r.h_final, h_flags: r.h_flags, h_score: r.h_score, h_err: r.h_err ?? null, h_detail: r.h_detail,
      });
    }
  }
  return out;
}

// ── 대시보드 집계 ──────────────────────────────────────────────────────────
export interface Cell3 { critical: number; n: number; over_abstain: number }
export interface AsrMatrix {
  attackers: string[]; defenders: string[];
  cells: Record<string, Record<string, { raw: Cell3 | null; harness: Cell3 | null }>>;
  totals: Record<string, { raw: Cell3; harness: Cell3 }>;
  errors: Record<string, number>;
}
const TUPLE_KEY = /^\(\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*'([^']*)'\s*\)$/;

function parseMatrix(cells: Record<string, [number, number, number]>, errors: Record<string, number> = {}): AsrMatrix | null {
  const m: AsrMatrix = { attackers: [], defenders: [], cells: {}, totals: {}, errors };
  let any = false;
  for (const [k, v] of Object.entries(cells)) {
    const mm = TUPLE_KEY.exec(k);
    if (!mm) continue;
    const [, att, def, mode] = mm;
    if (mode !== "raw" && mode !== "harness") continue;
    any = true;
    if (!m.attackers.includes(att)) m.attackers.push(att);
    if (!m.defenders.includes(def)) m.defenders.push(def);
    ((m.cells[att] ??= {})[def] ??= { raw: null, harness: null })[mode] = { critical: v[0], n: v[1], over_abstain: v[2] };
  }
  if (!any) return null;
  m.attackers.sort();
  for (const d of m.defenders) {
    const t = { raw: { critical: 0, n: 0, over_abstain: 0 }, harness: { critical: 0, n: 0, over_abstain: 0 } };
    for (const a of m.attackers) for (const mode of ["raw", "harness"] as const) {
      const c = m.cells[a]?.[d]?.[mode];
      if (c) { t[mode].critical += c.critical; t[mode].n += c.n; t[mode].over_abstain += c.over_abstain; }
    }
    m.totals[d] = t;
  }
  return m;
}

export interface HeatEntry { key: string; corpus: CorpusKey; stem: string; version: string; defender: string; mode: "raw" | "harness"; cells: Heat; source: string }

/** rows 파일 + 태그 → mech×target 히트맵 (run_asr.py / run_harness.py agg_mt 와 동일 규칙) */
function heatFromRows(rows: HRow[], tags: Map<string, Tag>, mode: "raw" | "harness"): Heat {
  const h: Heat = {};
  for (const r of rows) {
    const s = mode === "raw" ? r.raw_score : r.h_score;
    const t = tags.get(r.id);
    if (!s || !t || !t.mech || !t.target) continue;
    const cell = ((h[t.mech] ??= {})[t.target] ??= [0, 0]);
    cell[1] += 1; cell[0] += s.critical ? 1 : 0;
  }
  return h;
}
/** 태그 맵(파일 + 케이스 내장 태그) */
function fullTagMap(stem: string): Map<string, Tag> {
  const m = tagMap(stem);
  for (const c of loadJsonl<Case>(casesFile(stem === "attacks" ? "" : stem)) || []) { const t = tagOf(c, m); if (t && !m.has(c.id)) m.set(c.id, t); }
  return m;
}

/** 심사위원 첫 화면의 헤드라인 수치 — 결과 JSON 에서 직접 읽는다.
 *  숫자를 프론트엔드에 하드코딩하면 RESULTS.md/tables.md 와 다시 어긋나므로(과거에 실제로 발생)
 *  단일 출처를 유지한다. 정본: smoke/asr_local_*.json · smoke/harness_ko_local_*.json
 *  (같은 파일에서 smoke/summarize_results.py 가 tables.md 를 만든다). */
export function headlineNumbers() {
  const asrLocal = (served: string) => {
    const d = loadJson<{ cells?: Record<string, [number, number, number]> }>(`asr_local_${served}.json`);
    const cells = d?.cells;
    if (!cells) return null;
    let rawC = 0, rawN = 0, harC = 0, harN = 0;
    for (const [k, v] of Object.entries(cells)) {
      if (!Array.isArray(v) || v.length < 2) continue;
      if (k.includes("raw")) { rawC += v[0]; rawN += v[1]; }
      else if (k.includes("harness")) { harC += v[0]; harN += v[1]; }
    }
    return rawN ? { raw: { crit: rawC, n: rawN }, harness: { crit: harC, n: harN } } : null;
  };
  const koLocal = (served: string) => {
    const d = loadJson<Record<string, unknown>>(`harness_ko_local_${served}.json`);
    if (!d) return null;
    const rep = (d.report ?? d) as Record<string, { raw_crit: number; h_crit: number; n: number; n_scored?: number }>;
    for (const v of Object.values(rep)) {
      if (v && typeof v === "object" && "raw_crit" in v) {
        const n = v.n_scored ?? v.n;
        return { raw: { crit: v.raw_crit, n }, harness: { crit: v.h_crit, n } };
      }
    }
    return null;
  };
  // Wilson 95% 상한 — 0건일 때 "0%"가 아니라 상한을 함께 보여주기 위한 값
  const upper95 = (k: number, n: number) => {
    if (!n) return null;
    const z = 1.96, p = k / n, d = 1 + (z * z) / n;
    const c = p + (z * z) / (2 * n), m = z * Math.sqrt((p * (1 - p)) / n + (z * z) / (4 * n * n));
    return Math.round(((c + m) / d) * 1000) / 10;
  };
  return {
    frontier142: {
      "8b": asrLocal("qwen3-8b-awq"), "14b": asrLocal("qwen3-14b-awq"), "32b": asrLocal("qwen3-32b-awq"),
    },
    koThreshold88: {
      "8b": koLocal("qwen3-8b-awq"), "14b": koLocal("qwen3-14b-awq"), "32b": koLocal("qwen3-32b-awq"),
    },
    upper95,
  };
}

export function buildResults() {
  const files = listFiles();
  const sources = resultSources();
  const versions = [...new Set(sources.map((s) => s.version))].sort((a, b) => (a === "v1" ? 0 : a === "v2" ? 9 : 5) - (b === "v1" ? 0 : b === "v2" ? 9 : 5));

  // 실험1
  const exp1: Exp1Summary[] = [];
  for (const f of ["results_full.json", "results_q25.json"]) {
    const d = loadJson<Exp1File>(f);
    if (d?.summaries) exp1.push(...d.summaries);
  }

  // 실험2 raw → (v1 → v2.0 →) v2
  const exp2Src = sources.filter((s) => s.kind === "exp2");
  const exp2ByVer: Record<string, Record<string, HarnessResultsEntry> | null> = {};
  for (const s of exp2Src) exp2ByVer[s.version] = loadJson<Record<string, HarnessResultsEntry>>(s.agg);
  const exp2Versions = exp2Src.map((s) => s.version);
  const models = [...new Set(exp2Src.flatMap((s) => Object.keys(exp2ByVer[s.version] || {})))];
  const exp2 = models.map((m) => {
    const base = exp2Versions.map((v) => exp2ByVer[v]?.[m]).find(Boolean)!;
    const byVersion: Record<string, { h_crit: number; h_unnec: number; h_bycat: ByCat; flags: Record<string, number>; h_err: number | null } | null> = {};
    for (const v of exp2Versions) {
      const e = exp2ByVer[v]?.[m];
      byVersion[v] = e ? { h_crit: e.h_crit, h_unnec: e.h_unnec, h_bycat: e.h_bycat, flags: e.flags, h_err: e.h_err ?? null } : null;
    }
    return { model: m, n: base.n ?? null, raw_crit: base.raw_crit, raw_unnec: base.raw_unnec, raw_bycat: base.raw_bycat, byVersion, v1: byVersion.v1 ?? null, v2: byVersion.v2 ?? null };
  });
  const sum = (f: (x: typeof exp2[number]) => number) => exp2.reduce((s, x) => s + f(x), 0);
  const exp2Totals: Record<string, number | null> & { models: number } = {
    raw: sum((x) => x.raw_crit), raw_unnec: sum((x) => x.raw_unnec), models: models.length,
  };
  for (const v of exp2Versions) { exp2Totals[v] = sum((x) => x.byVersion[v]?.h_crit ?? 0); exp2Totals[`${v}_unnec`] = sum((x) => x.byVersion[v]?.h_unnec ?? 0); }
  for (const v of ["v1", "v2"]) if (!(v in exp2Totals)) { exp2Totals[v] = null; exp2Totals[`${v}_unnec`] = null; }

  // ASR 매트릭스: stem 별 × 버전
  const asr: Record<string, { corpus: CorpusKey; label: string; byVersion: Record<string, AsrMatrix | null>; sources: Record<string, string> }> = {};
  for (const s of sources.filter((x) => x.kind === "asr")) {
    const f = loadJson<AsrFile>(s.agg);
    const e = (asr[s.stem] ??= { corpus: s.corpus, label: `${CORPUS_LABEL[s.corpus]} (${s.stem})`, byVersion: {}, sources: {} });
    e.byVersion[s.version] = f ? parseMatrix(f.cells, f.errors) : null;
    e.sources[s.version] = s.agg;
  }
  const legacyCells: Record<string, [number, number, number]> = {};
  for (const f of ["asr_8b.json", "asr_32b.json"]) { const d = loadJson<Record<string, [number, number, number]>>(f); if (d) Object.assign(legacyCells, d); }
  const legacy = parseMatrix(legacyCells);

  // mech×target 히트맵 + 플래그 빈도: rows 파일에서 계산(정본), 없으면 집계 파일의 heat
  const heat: HeatEntry[] = [];
  const flags: Record<string, Record<string, number>> = {};
  for (const s of sources) {
    const rowsFile = s.rows ? loadJson<RowsFile>(s.rows) : null;
    if (rowsFile?.rows) {
      const tags = fullTagMap(s.stem);
      for (const [def, rows] of Object.entries(rowsFile.rows)) {
        for (const mode of ["raw", "harness"] as const) {
          const cells = heatFromRows(rows, tags, mode);
          if (Object.keys(cells).length) heat.push({ key: `${s.stem}|${s.version}|${def}|${mode}`, corpus: s.corpus, stem: s.stem, version: s.version, defender: def, mode, cells, source: s.rows! });
        }
        const cnt: Record<string, number> = {};
        for (const r of rows) for (const fl of r.h_flags || []) { const k = fl.split("→")[0]; cnt[k] = (cnt[k] || 0) + 1; }
        if (Object.keys(cnt).length) flags[`${s.kind === "exp2" ? "exp2" : "asr_" + s.stem}|${s.version}|${def}`] = cnt;
      }
      continue;
    }
    const agg = loadJson<AsrFile & Record<string, HarnessResultsEntry>>(s.agg);
    if (!agg) continue;
    if (s.kind === "asr") {
      for (const [k, cells] of Object.entries(agg.heat_mech_target || {})) {
        const [def, mode] = k.split("|");
        if ((mode === "raw" || mode === "harness") && cells && Object.keys(cells).length)
          heat.push({ key: `${s.stem}|${s.version}|${def}|${mode}`, corpus: s.corpus, stem: s.stem, version: s.version, defender: def, mode, cells, source: s.agg });
      }
    } else {
      for (const [def, e] of Object.entries(agg)) {
        const cells = (e as HarnessResultsEntry)?.h_mech_target;
        if (cells && Object.keys(cells).length) heat.push({ key: `${s.stem}|${s.version}|${def}|harness`, corpus: s.corpus, stem: s.stem, version: s.version, defender: def, mode: "harness", cells, source: s.agg });
        const fl = (e as HarnessResultsEntry)?.flags;
        if (fl && Object.keys(fl).length) flags[`exp2|${s.version}|${def}`] = fl;
      }
    }
  }

  // KPI
  const rate = (c: Cell3 | null | undefined) => (c && c.n ? c.critical / c.n : null);
  const fr = asr.frontier9;
  const kpiAsr = (def: string) => {
    const t2 = fr?.byVersion.v2?.totals[def], t1 = fr?.byVersion.v1?.totals[def], t20 = fr?.byVersion["v2.0"]?.totals[def], tl = legacy?.totals[def];
    const useLegacy = !fr?.byVersion.v2;
    return {
      raw: rate(t2?.raw ?? tl?.raw), v2: rate(useLegacy ? tl?.harness : t2?.harness), v1: rate(t1?.harness), "v2.0": rate(t20?.harness),
      n: (t2?.raw ?? tl?.raw)?.n ?? null, source: useLegacy ? "legacy" : "frontier9",
    };
  };
  const counts = corpusCounts();
  const kpi = {
    asr_8b: kpiAsr("qwen/qwen3-8b"), asr_32b: kpiAsr("qwen/qwen3-32b"),
    exp2: exp2Totals,
    corpus: { ...counts, total: Object.values(counts).reduce<number>((s, x) => s + (x || 0), 0) },
  };

  return {
    generated_at: new Date().toISOString(),
    files, sources, versions,
    kpi, exp1,
    exp2: { models: exp2, versions: exp2Versions, totals: exp2Totals, cats: ["clean", "threshold", "side", "negation", "amount", "quantity", "order_type", "abstain", "trajectory", "injection"] },
    asr, legacy,
    heat, flags,
    headline: headlineNumbers(),
  };
}
