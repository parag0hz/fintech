/**
 * OpenRouter 호출 (서버 전용). run.py call_openrouter 의 폴백 사다리를 그대로:
 *   strict json_schema → json_object → 순수 프롬프트.  4xx(429 제외)·non-JSON 출력 → 다음 모드,
 *   429/5xx/네트워크 → 같은 모드로 짧게 재시도. 성공한 모드는 모델별로 기억한다.
 *   qwen3 계열은 마지막 user 메시지에 " /no_think" 를 붙인다. temperature 0.
 */
import type { ChatMessage } from "./harness.js";
import { SYS, ORDER_SCHEMA, extractJson } from "./normalize.js";

const API_URL = "https://openrouter.ai/api/v1/chat/completions";
const MODE_CACHE = new Map<string, Mode>();

export type Mode = "schema" | "json_object" | "prompt";

export interface CallResult { pred: unknown; usage: Record<string, unknown>; mode: Mode }

export class RetryLater extends Error {}

class HttpError extends Error {
  constructor(public status: number, public body: string) { super(`HTTP ${status} ${body}`); }
}

export function apiKey(): string | null {
  const k = process.env.OPENROUTER_API_KEY?.trim();
  return k ? k : null;
}

/** raw(하네스 없음) 경로 메시지: run.py 와 동일하게 [배경 정보] 한 덩어리 + 발화 */
export function rawMessages(model: string, context: string | null | undefined, nl: string): ChatMessage[] {
  const user = /qwen3/i.test(model) ? nl + " /no_think" : nl;
  const msgs: ChatMessage[] = [{ role: "system", content: SYS }];
  if (context) msgs.push({ role: "user", content: "[배경 정보]\n" + context });
  msgs.push({ role: "user", content: user });
  return msgs;
}

function withNoThink(model: string, messages: ChatMessage[]): ChatMessage[] {
  const msgs = [...messages];
  const last = msgs[msgs.length - 1];
  if (/qwen3/i.test(model) && last && last.role === "user") {
    msgs[msgs.length - 1] = { role: "user", content: last.content + " /no_think" };
  }
  return msgs;
}

async function post(model: string, msgs: ChatMessage[], key: string, responseFormat: unknown, provider: unknown, timeoutMs: number, signal?: AbortSignal) {
  const body: Record<string, unknown> = { model, messages: msgs, temperature: 0 };
  if (responseFormat) body.response_format = responseFormat;
  if (provider) body.provider = provider;
  const ac = new AbortController();
  const timer = setTimeout(() => ac.abort(new Error("timeout")), timeoutMs);
  const onAbort = () => ac.abort(signal?.reason);
  signal?.addEventListener("abort", onAbort, { once: true });
  try {
    let res: Response;
    try {
      res = await fetch(API_URL, {
        method: "POST",
        headers: {
          Authorization: "Bearer " + key,
          "Content-Type": "application/json",
          "HTTP-Referer": "https://local.smoke-test",
          "X-Title": "nl2order-harness-web",
        },
        body: JSON.stringify(body),
        signal: ac.signal,
      });
    } catch (e) {
      throw new RetryLater("네트워크 오류: " + ((e as Error)?.message || String(e)).slice(0, 120));
    }
    if (!res.ok) {
      const txt = (await res.text().catch(() => "")).slice(0, 160);
      throw new HttpError(res.status, txt);
    }
    const data = (await res.json()) as { choices?: Array<{ message?: { content?: string } }>; usage?: Record<string, unknown> };
    if (!data.choices) throw new Error("no choices: " + JSON.stringify(data).slice(0, 140));
    const content = data.choices[0]?.message?.content || "";
    return { pred: extractJson(content), usage: data.usage || {} };
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", onAbort);
  }
}

export interface CallOptions { timeoutMs?: number; retries?: number; signal?: AbortSignal; schema?: Record<string, unknown> }

/**
 * messages 를 주면 그대로(하네스 프롬프트), 아니면 raw 프롬프트를 만든다.
 * 실패 시 Error(마지막 사유) throw. 429/5xx 는 retries 만큼 같은 모드로 재시도.
 */
export async function callOpenRouter(model: string, key: string, messages: ChatMessage[], opts: CallOptions = {}): Promise<CallResult> {
  const timeoutMs = opts.timeoutMs ?? 60_000;
  const retries = opts.retries ?? 2;
  const msgs = withNoThink(model, messages);
  const strict = { type: "json_schema", json_schema: { name: "order", strict: true, schema: opts.schema ?? ORDER_SCHEMA } };
  let modes: Array<[Mode, unknown, unknown]> = [
    ["schema", strict, { require_parameters: true }],
    ["json_object", { type: "json_object" }, null],
    ["prompt", null, null],
  ];
  const cached = MODE_CACHE.get(model);
  if (cached) modes = [...modes].sort((a, b) => (a[0] === cached ? 0 : 1) - (b[0] === cached ? 0 : 1));
  let last = "unknown";
  for (const [mode, rf, prov] of modes) {
    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        const { pred, usage } = await post(model, msgs, key, rf, prov, timeoutMs, opts.signal);
        MODE_CACHE.set(model, mode);
        return { pred, usage: { ...usage, _mode: mode }, mode };
      } catch (e) {
        if (opts.signal?.aborted) throw new Error("요청이 취소되었습니다.");
        if (e instanceof HttpError) {
          last = `HTTP ${e.status} ${e.body}`;
          if (e.status === 429 || e.status >= 500) {
            if (attempt < retries) { await sleep(1500 * (attempt + 1)); continue; }
            throw new Error(last);
          }
          break;                                   // 4xx(파라미터 미지원 등) → 다음 모드
        }
        if (e instanceof RetryLater) {
          last = e.message;
          if (attempt < retries) { await sleep(1500 * (attempt + 1)); continue; }
          throw new Error(last);
        }
        if (e instanceof SyntaxError) { last = "non-JSON output"; break; }   // 이 모드 출력이 JSON 아님 → 완화 모드
        throw e;                                   // 'no choices' 등 구조 오류는 즉시 실패(run.py 와 동일)
      }
    }
  }
  throw new Error(last);
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
