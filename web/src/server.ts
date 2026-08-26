/**
 * Express 서버: 정적 UI(public/) + API.
 *   POST /api/parse      raw vs 하네스 파싱 (LLM 2콜, 병렬)  — 키 없으면 503 + 규칙 미리보기
 *   GET  /api/analyze    결정적 단서 분석만 (LLM 없음, 타이핑 중 하이라이트용)
 *   GET  /api/corpus     공격 코퍼스(+태그)
 *   GET  /api/case/:id   케이스 상세 + 방어자별 결과
 *   GET  /api/results    대시보드 집계
 *   GET  /api/health
 */
import express, { type Request, type Response, type NextFunction } from "express";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { analyzeUtterance, buildMessages, deterministicCheck, historyOrder, historyText, EMPTY_ORDER, HARNESS_SCHEMA, type HistoryInput, type Order, type FlipPolicy, type Position } from "./harness.js";
import { normalize } from "./normalize.js";
import { apiKey, callOpenRouter, rawMessages } from "./openrouter.js";
import { fallbackParse, loadStocks } from "./fallback.js";
import { WEB_ROOT, buildResults, caseOutcomes, findCase, loadCorpus, corpusCounts, corpusStems, locate, type CorpusKey, CORPUS_LABEL } from "./data.js";

// ── .env (의존성 없이) : web/.env → SMOKE_DIR/.env 순으로 읽되, 이미 있는 환경변수는 덮지 않는다 ──
function loadDotenv(p: string) {
  if (!existsSync(p)) return;
  for (let line of readFileSync(p, "utf-8").split(/\r?\n/)) {
    line = line.trim();
    if (!line || line.startsWith("#")) continue;
    if (line.startsWith("export ")) line = line.slice(7).trim();
    const i = line.indexOf("=");
    if (i < 0) continue;
    const k = line.slice(0, i).trim(), v = line.slice(i + 1).trim().replace(/^["']|["']$/g, "");
    if (k && !(k in process.env)) process.env[k] = v;
  }
}
loadDotenv(path.join(WEB_ROOT, ".env"));
loadDotenv(path.resolve(WEB_ROOT, process.env.SMOKE_DIR || "../smoke", ".env"));

const PORT = Number(process.env.PORT || 3000);
const DEFAULT_MODEL = process.env.DEFENDER_MODEL || "qwen/qwen3-8b";
const DAILY_CAP = Math.max(0, Number(process.env.DAILY_CALL_CAP || 500));
const RATE_PER_MIN = Math.max(1, Number(process.env.RATE_PER_MIN || 20));
const LLM_TIMEOUT_MS = Math.max(5000, Number(process.env.LLM_TIMEOUT_MS || 60000));
export const MODELS = [
  "qwen/qwen3-8b", "qwen/qwen3-14b", "qwen/qwen3-32b", "qwen/qwen3-30b-a3b", "qwen/qwen-2.5-72b-instruct",
];
if (!MODELS.includes(DEFAULT_MODEL)) MODELS.unshift(DEFAULT_MODEL);

const MAX_UTT = 500, MAX_HIST = 2000, MAX_CTX = 3000;

// ── 호출 제한: IP 별 분당 + 프로세스 전체 일일 상한 ──
const ipHits = new Map<string, number[]>();
let dayKey = "", dayCalls = 0;
function todayKey() { return new Date().toISOString().slice(0, 10); }
function reserveCalls(n: number): boolean {
  const k = todayKey();
  if (k !== dayKey) { dayKey = k; dayCalls = 0; }
  if (dayCalls + n > DAILY_CAP) return false;
  dayCalls += n;
  return true;
}
// 상류(OpenRouter)가 실패하면 선차감분을 돌려준다. 환불하지 않으면 상류의 일시 장애가
// "성공 0건인데 예산만 소진" → 회복 후에도 UTC 자정까지 전면 429 라는 하루짜리
// 자기유발 장애로 고착된다. 심사 무중단 요건(9/7~9/11)에 직결된다.
function refundCalls(n: number): void {
  if (todayKey() === dayKey) dayCalls = Math.max(0, dayCalls - n);
}
function rateLimited(ip: string): boolean {
  const now = Date.now();
  const arr = (ipHits.get(ip) || []).filter((t) => now - t < 60_000);
  if (arr.length >= RATE_PER_MIN) { ipHits.set(ip, arr); return true; }
  arr.push(now); ipHits.set(ip, arr);
  return false;
}
setInterval(() => { const now = Date.now(); for (const [ip, arr] of ipHits) { const a = arr.filter((t) => now - t < 60_000); if (a.length) ipHits.set(ip, a); else ipHits.delete(ip); } }, 5 * 60_000).unref();

// ── 입력 정리 ──
function parseHistory(h: unknown): HistoryInput {
  if (h == null) return null;
  if (typeof h === "string") {
    const s = h.trim();
    if (!s) return null;
    if (s.startsWith("[") || s.startsWith("{")) { try { return parseHistory(JSON.parse(s)); } catch { /* 일반 텍스트로 */ } }
    const lines = s.split(/\r?\n/).map((x) => x.trim()).filter(Boolean);
    return lines.length <= 1 ? (lines[0] ?? null) : lines;
  }
  if (Array.isArray(h)) {
    const items = h.filter((x) => typeof x === "string" ? x.trim() : (x && typeof x === "object")).map((x) => typeof x === "string" ? x.trim() : x as Order);
    return items.length ? items : null;
  }
  if (typeof h === "object") return h as Order;
  return null;
}
function historyLen(h: HistoryInput): number { return JSON.stringify(h ?? "").length; }

const app = express();
// trust proxy=true 는 X-Forwarded-For 체인 전체를 신뢰해 req.ip 가 요청자가 보낸 값이 된다.
// 그러면 헤더를 매번 바꾸는 것만으로 IP 분당 제한이 무력화되고, 남은 방어선인 일일 상한을
// 한 클라이언트가 수 초에 고갈시킬 수 있다. 실제 프록시 홉 수만 신뢰한다(기본 1, 직접 노출이면 0).
app.set("trust proxy", Math.max(0, Number(process.env.TRUST_PROXY_HOPS ?? 1)));
app.disable("x-powered-by");
app.use(express.json({ limit: "64kb" }));
app.use((_req, res, next) => { res.setHeader("Cache-Control", "no-store"); next(); });

const asyncH = (fn: (req: Request, res: Response) => Promise<unknown>) => (req: Request, res: Response, next: NextFunction) => fn(req, res).catch(next);

app.get("/api/health", (_req, res) => {
  res.json({
    ok: true, service: "nl2order-harness-web", time: new Date().toISOString(),
    has_key: !!apiKey(), default_model: DEFAULT_MODEL, models: MODELS,
    daily_cap: DAILY_CAP, daily_used: todayKey() === dayKey ? dayCalls : 0,
    data: { attacks: locate("attacks.jsonl"), counts: corpusCounts() },
  });
});

app.get("/api/analyze", (req, res) => {
  const utterance = String(req.query.utterance ?? "").slice(0, MAX_UTT);
  const history = parseHistory(req.query.history ?? null);
  const a = analyzeUtterance(utterance);
  const hist = historyOrder(history);
  const anyFlip = a.flip.length > 0 || a.cond_flip.length > 0;
  a.history = hist;
  a.flip_side = anyFlip && (a.flip_both || !a.flip_cond_only);
  a.flip_cond = anyFlip && (a.flip_both || a.flip_cond_only || a.cond_flip.length > 0);
  // 규칙 미리보기: 빈 주문에 L3 만 적용했을 때의 플래그
  const preview = deterministicCheck(utterance, history, { ...EMPTY_ORDER });
  res.json({ utterance, analysis: a, history_text: historyText(history), preview_flags: preview.flags });
});

app.get("/api/corpus", (req, res) => {
  const file = String(req.query.file ?? "attacks") as CorpusKey;
  if (!(file in CORPUS_LABEL)) { res.status(400).json({ error: "file 은 attacks|frontier9|adaptive 중 하나여야 합니다." }); return; }
  const cases = loadCorpus(file);
  if (!cases) { res.status(404).json({ error: `${file} 코퍼스 파일이 없습니다.`, file, cases: [] }); return; }
  res.json({ file, label: CORPUS_LABEL[file], stems: corpusStems()[file], n: cases.length, cases });
});

app.get("/api/case/:id", (req, res) => {
  const id = String(req.params.id);
  const c = findCase(id);
  if (!c) { res.status(404).json({ error: `케이스 ${id} 를 찾을 수 없습니다.` }); return; }
  res.json({ case: c, outcomes: caseOutcomes(id) });
});

app.get("/api/results", (_req, res) => {
  res.json(buildResults());
});

app.get("/api/stocks", (_req, res) => { res.json({ stocks: loadStocks() }); });

interface ParseBody { utterance?: unknown; history?: unknown; context?: unknown; model?: unknown; flip_policy?: unknown; positions?: unknown }

/** 계좌 포지션(신뢰 채널): [{ticker, quantity, avg_price}] — 퍼센트 손익의 기준가/수량 해소에만 쓴다. 최대 50개, 숫자만 통과. */
function parsePositions(v: unknown): Position[] | null {
  if (!Array.isArray(v)) return null;
  const out: Position[] = [];
  for (const it of v.slice(0, 50)) {
    if (!it || typeof it !== "object") continue;
    const o = it as Record<string, unknown>;
    const ticker = typeof o.ticker === "string" ? o.ticker.slice(0, 40) : null;
    const quantity = Number(o.quantity), avg = Number(o.avg_price);
    if (!ticker) continue;
    out.push({ ticker, quantity: Number.isFinite(quantity) && quantity > 0 ? Math.trunc(quantity) : undefined,
               avg_price: Number.isFinite(avg) && avg > 0 ? avg : undefined });
  }
  return out.length ? out : null;
}

app.post("/api/parse", asyncH(async (req, res) => {
  const b = (req.body || {}) as ParseBody;
  const utterance = typeof b.utterance === "string" ? b.utterance.trim() : "";
  if (!utterance) { res.status(400).json({ error: "utterance(발화)가 비어 있습니다." }); return; }
  if (utterance.length > MAX_UTT) { res.status(400).json({ error: `발화는 ${MAX_UTT}자 이하여야 합니다.` }); return; }
  const history = parseHistory(b.history);
  if (historyLen(history) > MAX_HIST) { res.status(400).json({ error: `직전 대화는 ${MAX_HIST}자 이하여야 합니다.` }); return; }
  const positions = parsePositions(b.positions);
  const context = typeof b.context === "string" && b.context.trim() ? b.context.trim() : null;
  if (context && context.length > MAX_CTX) { res.status(400).json({ error: `외부 문맥은 ${MAX_CTX}자 이하여야 합니다.` }); return; }
  const model = typeof b.model === "string" && MODELS.includes(b.model) ? b.model : DEFAULT_MODEL;
  const flipPolicy: FlipPolicy = b.flip_policy === "confirm" ? "confirm" : "commit";
  const harnessMsgs = buildMessages({ nl: utterance, history, context });

  const key = apiKey();
  if (!key) {
    // 키 없음: 모델 대신 예비 규칙 파서로 8필드를 채우고 L3 를 적용한다(화면이 막히지 않도록). raw = 예비 파서 출력 그대로.
    const t0 = Date.now();
    const fb = fallbackParse(utterance, history);
    const { final, flags, detail } = deterministicCheck(utterance, history, { ...fb }, flipPolicy, positions);
    res.json({
      degraded: "no_key", preview: true, fallback: true, model, ms: Date.now() - t0,
      warning: "OPENROUTER_API_KEY 가 설정되지 않아 모델 대신 예비 규칙 파서를 사용했습니다(규칙 미리보기).",
      raw: { pred: fb, raw_json: null, mode: "fallback", ms: 0, err: "API 키 없음(예비 규칙 파서)" },
      harness: { parsed: { ...fb }, final, flags, detail, raw_json: null, mode: "fallback", ms: Date.now() - t0, err: null, fallback: true },
      messages: harnessMsgs, raw_messages: [], flip_policy: flipPolicy,
    });
    return;
  }
  const ip = req.ip || req.socket.remoteAddress || "?";
  if (rateLimited(ip)) { res.status(429).json({ error: `요청이 너무 잦습니다. 분당 ${RATE_PER_MIN}회까지 가능합니다. 잠시 후 다시 시도해 주세요.` }); return; }
  if (!reserveCalls(2)) {
    // 상한 도달 시 429 로 화면을 막지 않는다 — 심사 기간에 데모가 죽는 것이 가장 큰 위험이다.
    // 키 없음 경로와 동일하게 예비 규칙 파서 + L3 로 200 을 돌려주고, 상한 도달만 알린다.
    const t0 = Date.now();
    const fb = fallbackParse(utterance, history);
    const { final, flags, detail } = deterministicCheck(utterance, history, { ...fb }, flipPolicy, positions);
    res.json({
      degraded: "daily_cap", preview: true, fallback: true, model, ms: Date.now() - t0,
      warning: `오늘의 모델 호출 상한(${DAILY_CAP}회)에 도달해 예비 규칙 파서로 응답했습니다. 하네스(L3) 판정은 동일하게 적용됩니다.`,
      raw: { pred: fb, raw_json: null, mode: "fallback", ms: 0, err: "일일 상한 도달(예비 규칙 파서)" },
      harness: { parsed: { ...fb }, final, flags, detail, raw_json: null, mode: "fallback", ms: Date.now() - t0, err: null, fallback: true },
      messages: harnessMsgs, raw_messages: [], flip_policy: flipPolicy,
    });
    return;
  }

  // raw 경로: run_harness.raw_call 과 동일 — history 도 '[배경 정보]' 한 덩어리로
  let rawCtx = context;
  const ht = historyText(history);
  if (ht) rawCtx = "직전 대화: " + ht + (context ? "\n" + context : "");
  const rawMsgs = rawMessages(model, rawCtx, utterance);

  const t0 = Date.now();
  const rawP = (async () => {
    const t = Date.now();
    try {
      const r = await callOpenRouter(model, key, rawMsgs, { timeoutMs: LLM_TIMEOUT_MS });
      return { pred: normalize(r.pred), raw_json: r.pred, mode: r.mode, ms: Date.now() - t, err: null as string | null, usage: r.usage };
    } catch (e) {
      return { pred: null, raw_json: null, mode: null, ms: Date.now() - t, err: String((e as Error).message || e).slice(0, 200), usage: null };
    }
  })();
  const harP = (async () => {
    const t = Date.now();
    let parsed: Order | null = null, mode: string | null = null, err: string | null = null, raw_json: unknown = null, usage: unknown = null;
    try {
      const r = await callOpenRouter(model, key, harnessMsgs, { timeoutMs: LLM_TIMEOUT_MS, schema: HARNESS_SCHEMA });
      raw_json = r.pred; mode = r.mode; usage = r.usage;
      parsed = normalize(r.pred);
    } catch (e) {
      err = String((e as Error).message || e).slice(0, 200);
    }
    let fallback = false;
    if (parsed === null) { parsed = fallbackParse(utterance, history); fallback = true; }   // 모델 응답 없음 → 예비 규칙 파서 → L3
    const { final, flags, detail } = deterministicCheck(utterance, history, parsed, flipPolicy, positions);
    return { parsed, final, flags, detail, raw_json, mode: fallback ? "fallback" : mode, ms: Date.now() - t, err, usage, fallback };
  })();
  const [raw, harness] = await Promise.all([rawP, harP]);
  // 실패한 호출은 과금되지 않으므로 예산을 돌려준다(선차감 후 환불 없음 = 자기유발 장애).
  const failed = (raw.err ? 1 : 0) + (harness.err ? 1 : 0);
  if (failed) refundCalls(failed);
  const degraded = harness.fallback ? "llm_error" : undefined;
  res.json({
    model, ms: Date.now() - t0, raw, harness, messages: harnessMsgs, raw_messages: rawMsgs, flip_policy: flipPolicy,
    degraded, fallback: !!harness.fallback,
    warning: degraded ? `모델 호출에 실패해 예비 규칙 파서를 사용했습니다 (${harness.err ?? ""})` : undefined,
  });
}));

// ── 정적 UI ──
const PUBLIC = path.join(WEB_ROOT, "public");
app.use(express.static(PUBLIC, { etag: true, maxAge: 0 }));
app.get(/^\/(?!api\/).*/, (_req, res) => res.sendFile(path.join(PUBLIC, "index.html")));

app.use((err: unknown, _req: Request, res: Response, _next: NextFunction) => {
  const msg = err instanceof SyntaxError ? "요청 본문(JSON)을 해석할 수 없습니다." : "서버 내부 오류가 발생했습니다.";
  if (!(err instanceof SyntaxError)) console.error(err);
  res.status(err instanceof SyntaxError ? 400 : 500).json({ error: msg });
});

app.listen(PORT, () => {
  console.log(`nl2order harness web → http://localhost:${PORT}  (key: ${apiKey() ? "있음" : "없음"}, 데이터: ${locate("attacks.jsonl") ?? "없음"})`);
});
