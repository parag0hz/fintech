/**
 * 예비 규칙 파서 — 모델 응답이 없을 때(키 없음·호출 실패) 화면이 막히지 않도록 발화에서 8필드를 규칙으로 뽑는다.
 * 방향/조건/보류는 어차피 L3(deterministicCheck)가 문자 그대로 결정하므로, 여기서는 종목·수량·금액·가격·주문유형만 성실히 채운다.
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import { analyzeUtterance, type Order, type HistoryInput } from "./harness.js";
import { korNum } from "./normalize.js";
import { WEB_ROOT } from "./data.js";

export interface Stock { name: string; code: string; base: number; aliases?: string[] }

let stocksCache: Stock[] | null = null;
export function loadStocks(): Stock[] {
  if (stocksCache) return stocksCache;
  try {
    stocksCache = (JSON.parse(readFileSync(path.join(WEB_ROOT, "public", "stocks.json"), "utf-8")) as { stocks: Stock[] }).stocks;
  } catch { stocksCache = []; }
  return stocksCache;
}

/** 발화에서 종목 하나를 찾는다: 6자리 코드 → 이름/별칭(긴 것 우선, 대소문자 무시) */
export function findTicker(text: string, stocks: Stock[] = loadStocks()): { name: string; code: string } | null {
  const code = /(?<!\d)(\d{6})(?!\d)/.exec(text);
  if (code) { const s = stocks.find((x) => x.code === code[1]); if (s) return { name: s.name, code: s.code }; }
  const low = text.toLowerCase();
  const cands: Array<{ key: string; s: Stock }> = [];
  for (const s of stocks) for (const k of [s.name, ...(s.aliases || [])]) cands.push({ key: k.toLowerCase(), s });
  cands.sort((a, b) => b.key.length - a.key.length);
  for (const c of cands) if (low.includes(c.key)) return { name: c.s.name, code: c.s.code };
  return null;
}

const NUM = /(\d[\d,]*(?:\.\d+)?\s*(?:억|만|천)?(?:\s*\d[\d,]*\s*(?:억|만|천))*)\s*(원어치|어치|원\s*어치|주|개|원)?/g;
const SKIP_AFTER = /^\s*(?:분|일|시|초|번|개월|월|년|%|퍼|배|틱|호가|단)/;
const MARKET_CUE = /시장가|현재가|호가\s*그대로|지금\s*가격|현재\s*가격|시가/;

/** 이력(구조화 dict) 중 가장 최근 주문 — 참조 발화("그거 …")에서 종목·수량 승계용 */
function lastHistoryOrder(history: HistoryInput): Order | null {
  const items = !history ? [] : Array.isArray(history) ? history : [history];
  for (let i = items.length - 1; i >= 0; i--) {
    const h = items[i];
    if (h && typeof h === "object" && !Array.isArray(h)) return h as Order;
  }
  return null;
}

/** 규칙 기반 8필드 추출. 방향/조건은 단서로만(없으면 null/NONE) — L3가 다시 결정한다.
 *  참조 표현("그거/방금/반대로")이 있고 구조화 이력이 있으면 종목·수량·가격·유형을 직전 주문에서 승계한다. */
export function fallbackParse(utterance: string, history: HistoryInput = null): Order {
  const t = utterance || "";
  const tk = findTicker(t);
  let quantity: number | null = null, amount: number | null = null, price: number | null = null;
  NUM.lastIndex = 0;
  for (const m of t.matchAll(NUM)) {
    const raw = m[1].trim(), suf = (m[2] || "").replace(/\s/g, "");
    if (/^\d{6}$/.test(raw.replace(/,/g, ""))) continue;               // 종목코드
    const after = t.slice(m.index! + m[0].length);
    if (!suf && SKIP_AFTER.test(after)) continue;                        // 10분, 3일 …
    const v = korNum(raw);
    if (typeof v !== "number") continue;
    if (suf === "주" || suf === "개") { if (quantity === null) quantity = Math.trunc(v); }
    else if (suf.includes("어치")) { if (amount === null) amount = v; }
    else if (suf === "원") { if (price === null) price = v; }
    else if (/^\s*(?:에|이하|이상|미만|초과|아래|밑|위|넘|깨|되면|이면|찍|도달|근처|선|대|부근|정도|까지|이|가|으로|로)/.test(after) || /(?:억|만|천)\s*$/.test(raw)) {
      if (price === null) price = v;
    } else if (quantity === null && v < 100000 && Number.isInteger(v) && !/(?:억|만|천)/.test(raw) && /^\s*(?:$|[\s,.]|매수|매도|사|팔|담|정리|처분|손절|익절|시장가|지정가)/.test(after)) {
      quantity = Math.trunc(v);                                          // "삼성 10 매수" 처럼 단위 없는 수량
    }
  }
  const a = analyzeUtterance(t);
  const market = MARKET_CUE.test(t);
  let order_type: string | null = market ? "MARKET" : price !== null ? "LIMIT" : null;
  let ticker: unknown = tk ? tk.name : null;
  const ref = a.ref.length > 0 || a.flip.length > 0 || a.cond_flip.length > 0;
  const last = ref ? lastHistoryOrder(history) : null;
  if (last) {
    if (ticker === null && last.ticker) ticker = last.ticker;
    if (quantity === null && amount === null) { if (typeof last.quantity === "number") quantity = last.quantity; else if (typeof last.amount === "number") amount = last.amount; }
    if (price === null && typeof last.price === "number" && !market) price = last.price;
    if (order_type === null && typeof last.order_type === "string") order_type = last.order_type;
  }
  if (order_type === null) order_type = price !== null ? "LIMIT" : "MARKET";
  return {
    ticker, side: a.side, order_type,
    quantity, amount, price, condition: a.cond || "NONE", abstain: false,
  };
}
