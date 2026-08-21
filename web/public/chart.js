// chart.js — 인라인 SVG 캔들 차트 (프레임워크 없음)
//  · makeSeries(): 종목코드+타임프레임으로 시드된 결정적 모의 시계열(150~200봉)
//  · createChart(host): 캔들·이동평균(MA5/20/60)·거래량 서브패널·가격/시간 축·십자선(rAF 스로틀)·오버레이 라인·휠 줌/드래그 팬
// 색상은 CSS 변수(--up/--down/--ma5 …)를 그대로 참조하므로 라이트/다크 모두 동작한다.

const won = (n) => n == null || Number.isNaN(n) ? "—" : Math.round(n).toLocaleString("ko-KR");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pad2 = (n) => String(n).padStart(2, "0");

export const TIMEFRAMES = [
  { key: "1m", label: "1분", stepMs: 60_000, vol: 0.0011, n: 200, intraday: true },
  { key: "10m", label: "10분", stepMs: 600_000, vol: 0.0028, n: 180, intraday: true },
  { key: "1d", label: "일", stepMs: 86_400_000, vol: 0.013, n: 180 },
  { key: "1w", label: "주", stepMs: 7 * 86_400_000, vol: 0.026, n: 160 },
  { key: "1M", label: "월", stepMs: 30 * 86_400_000, vol: 0.05, n: 150 },
];
export const tfByKey = (k) => TIMEFRAMES.find((t) => t.key === k) || TIMEFRAMES[2];

// ── 결정적 난수 ──────────────────────────────────────────────────────
function hashStr(s) { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }
function mulberry(seed) { let a = seed >>> 0; return () => { a = (a + 0x6D2B79F5) | 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
const gauss = (r) => { const u = Math.max(1e-9, r()), v = r(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); };

export function tickSize(p) { return p < 2000 ? 1 : p < 5000 ? 5 : p < 20000 ? 10 : p < 50000 ? 50 : p < 200000 ? 100 : p < 500000 ? 500 : 1000; }
export function roundTick(p) { const t = tickSize(p); return Math.round(p / t) * t; }

/** 시각 배열: 지금부터 거꾸로 n개. 분봉은 09:00~15:30 장중만, 주말 건너뜀. */
function timeline(tf, n) {
  const out = [];
  if (tf.intraday) {
    let t = new Date(); t.setSeconds(0, 0); t.setMinutes(Math.floor(t.getMinutes() / (tf.stepMs / 60000)) * (tf.stepMs / 60000));
    const inSession = (d) => { const m = d.getHours() * 60 + d.getMinutes(); return m >= 540 && m <= 930 && d.getDay() >= 1 && d.getDay() <= 5; };
    const backToClose = (d) => { do { d.setDate(d.getDate() - 1); } while (d.getDay() === 0 || d.getDay() === 6); d.setHours(15, 30, 0, 0); };
    if (!inSession(t)) { if (t.getHours() * 60 + t.getMinutes() > 930 && t.getDay() >= 1 && t.getDay() <= 5) t.setHours(15, 30, 0, 0); else backToClose(t); }
    for (let i = 0; i < n; i++) { out.push(t.getTime()); t = new Date(t.getTime() - tf.stepMs); if (!inSession(t)) backToClose(t); }
    return out.reverse();
  }
  const t = new Date(); t.setHours(0, 0, 0, 0);
  for (let i = 0; i < n; i++) {
    out.push(t.getTime());
    if (tf.key === "1d") { do { t.setDate(t.getDate() - 1); } while (t.getDay() === 0 || t.getDay() === 6); }
    else if (tf.key === "1w") t.setDate(t.getDate() - 7);
    else t.setMonth(t.getMonth() - 1);
  }
  return out.reverse();
}

/**
 * 모의 시계열. history 봉은 시드된 랜덤워크(약한 평균회귀 + 국면 추세)를 prev(전일 종가)에 맞춰 스케일하고,
 * 마지막 봉은 '지금' 봉(시가 ≈ prev, 종가 = live). 분봉은 전 구간을 prev→live 로 이어 붙인다.
 */
export function makeSeries({ code, prev, live, tf }) {
  const n = tf.n, r = mulberry(hashStr(`${code}|${tf.key}`));
  const closes = [], vols = [];
  let p = prev, regime = 0;
  for (let i = 0; i < n; i++) {
    if (i % 23 === 0) regime = (r() - 0.5) * tf.vol * 0.5;
    const shock = gauss(r) * tf.vol + regime + (prev - p) / prev * 0.035;
    p = Math.max(prev * 0.4, p * (1 + shock));
    closes.push(p); vols.push(0.6 + Math.abs(gauss(r)) * 0.9);
  }
  const hist = tf.intraday ? n : n - 1;
  const first = closes[0], last = closes[hist - 1];
  const candles = [];
  for (let i = 0; i < hist; i++) {
    // 분봉: 시작 ≈ prev(전일 종가) → 끝 = live 로 선형 브리지 · 일/주/월: 마지막 과거 봉 종가 = prev 가 되도록 스케일
    const c = tf.intraday
      ? closes[i] * (prev / first) + (live - last * (prev / first)) * (i / Math.max(1, hist - 1))
      : closes[i] * (prev / last);
    const o = i === 0 ? c * (1 + gauss(r) * tf.vol * 0.3) : candles[i - 1].c;
    const wick = Math.abs(gauss(r)) * tf.vol * 0.7;
    const h = Math.max(o, c) * (1 + wick * r()), l = Math.min(o, c) * (1 - wick * r());
    candles.push({ o: roundTick(o), h: roundTick(h), l: roundTick(l), c: roundTick(c), v: 0 });
  }
  if (!tf.intraday) {
    const o = roundTick(prev * (1 + gauss(r) * tf.vol * 0.25));
    candles.push({ o, h: Math.max(o, live), l: Math.min(o, live), c: live, v: 0, live: true });
  } else candles[candles.length - 1].live = true;
  candles[candles.length - 1].c = live;
  // 거래량: 가격대에 반비례한 기본량 × 봉 길이
  const baseVol = tf.intraday ? 2.4e8 / prev * (tf.key === "1m" ? 1 : 8) : 3.5e9 / prev * (tf.key === "1d" ? 1 : tf.key === "1w" ? 5 : 20);
  const times = timeline(tf, candles.length);
  candles.forEach((k, i) => { k.t = times[i]; k.v = Math.round(baseVol * vols[i] * (1 + Math.abs(k.c - k.o) / k.o / tf.vol)); });
  return candles;
}

/** 이동평균 (앞쪽은 null) */
function ma(candles, w) { const out = new Array(candles.length).fill(null); let s = 0; for (let i = 0; i < candles.length; i++) { s += candles[i].c; if (i >= w) s -= candles[i - w].c; if (i >= w - 1) out[i] = s / w; } return out; }

/** '예쁜' 가격 눈금 간격 */
function niceStep(range, target = 6) {
  const raw = range / target, mag = Math.pow(10, Math.floor(Math.log10(raw)));
  for (const m of [1, 2, 2.5, 5, 10]) if (raw <= m * mag) return m * mag;
  return 10 * mag;
}
const fmtTime = (ts, tf, full = false) => {
  const d = new Date(ts);
  if (tf.intraday) return full ? `${d.getMonth() + 1}/${d.getDate()} ${pad2(d.getHours())}:${pad2(d.getMinutes())}` : `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
  if (tf.key === "1M") return `${d.getFullYear()}/${pad2(d.getMonth() + 1)}`;
  return full ? `${d.getFullYear()}/${pad2(d.getMonth() + 1)}/${pad2(d.getDate())}` : `${pad2(d.getMonth() + 1)}/${pad2(d.getDate())}`;
};
const volTxt = (v) => v >= 1e8 ? (v / 1e8).toFixed(1) + "억" : v >= 1e4 ? Math.round(v / 1e4).toLocaleString("ko-KR") + "만" : won(v);

/**
 * 차트 생성. host 는 position:relative 인 블록. 반환 api:
 *  setSeries(candles, tf) · setLive(price) · setOverlays([{price,label,color,dash,tag}]) · setIndicators({ma5,ma20,ma60,vol}) · destroy()
 */
export function createChart(host) {
  host.classList.add("cchart");
  host.innerHTML = `<svg class="cc-svg" xmlns="http://www.w3.org/2000/svg"><g class="cc-main"></g><g class="cc-xh" style="display:none"></g></svg><div class="cc-ohlc"></div><div class="cc-empty">차트 준비 중…</div>`;
  const svg = host.querySelector("svg"), gMain = host.querySelector(".cc-main"), gXh = host.querySelector(".cc-xh"), ohlcBox = host.querySelector(".cc-ohlc"), emptyBox = host.querySelector(".cc-empty");
  const st = { candles: [], tf: TIMEFRAMES[2], vs: 0, ve: 0, overlays: [], ind: { ma5: true, ma20: true, ma60: true, vol: true }, geo: null, mas: {}, hover: null, drag: null, raf: 0, pendingMove: null };
  const PAD = { l: 6, r: 66, t: 8, b: 20, gap: 8 };

  function geometry() {
    const W = host.clientWidth || 600, H = host.clientHeight || 300;
    const showVol = st.ind.vol;
    const innerH = H - PAD.t - PAD.b;
    const priceH = showVol ? Math.round(innerH * 0.76) : innerH;
    const volTop = PAD.t + priceH + PAD.gap, volH = showVol ? H - PAD.b - volTop : 0;
    const vis = st.candles.slice(st.vs, st.ve);
    let lo = Infinity, hi = -Infinity, vmax = 1;
    for (const k of vis) { if (k.l < lo) lo = k.l; if (k.h > hi) hi = k.h; if (k.v > vmax) vmax = k.v; }
    for (const key of ["ma5", "ma20", "ma60"]) if (st.ind[key]) for (let i = st.vs; i < st.ve; i++) { const m = st.mas[key]?.[i]; if (m != null) { if (m < lo) lo = m; if (m > hi) hi = m; } }
    if (!Number.isFinite(lo)) { lo = 0; hi = 1; }
    // 오버레이(평단·조건가)는 캔들 범위의 ±50% 안이면 축을 넓혀 포함, 그 밖이면 가장자리에 핀 표시만
    const span = Math.max(hi - lo, tickSize(hi) * 4), lo0 = lo, hi0 = hi;
    for (const o of st.overlays) if (o.price != null && Number.isFinite(o.price)) { if (o.price < lo && o.price >= lo0 - span * 0.5) lo = o.price; if (o.price > hi && o.price <= hi0 + span * 0.5) hi = o.price; }
    const padP = Math.max((hi - lo) * 0.06, tickSize(hi) * 2);
    lo -= padP; hi += padP;
    const cw = (W - PAD.l - PAD.r) / Math.max(1, st.ve - st.vs);
    return { W, H, priceH, volTop, volH, lo, hi, vmax, cw, showVol,
      x: (i) => PAD.l + (i - st.vs + 0.5) * cw,
      y: (p) => PAD.t + (hi - p) / (hi - lo) * priceH,
      yInv: (py) => hi - (py - PAD.t) / priceH * (hi - lo),
      yv: (v) => volTop + volH - (v / vmax) * volH };
  }

  function render() {
    if (!st.candles.length) { emptyBox.style.display = ""; gMain.innerHTML = ""; return; }
    emptyBox.style.display = "none";
    const g = st.geo = geometry();
    const { W, H, cw } = g;
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`); svg.setAttribute("width", W); svg.setAttribute("height", H);
    const parts = [];
    // ── 가격 격자 + 우측 축
    const step = niceStep(g.hi - g.lo, 8);
    const p0 = Math.ceil(g.lo / step) * step;
    for (let p = p0; p <= g.hi; p += step) {
      const y = g.y(p).toFixed(1);
      parts.push(`<line class="grid" x1="${PAD.l}" x2="${W - PAD.r}" y1="${y}" y2="${y}"/><text class="ax" x="${W - PAD.r + 6}" y="${+y + 4}">${won(p)}</text>`);
    }
    // ── 시간 격자 + 하단 축 (약 7개 라벨)
    const nvis = st.ve - st.vs, every = Math.max(1, Math.round(nvis / 7));
    let lastDay = null;
    for (let i = st.vs; i < st.ve; i++) {
      if ((i - st.vs) % every !== 0) continue;
      const x = g.x(i).toFixed(1); if (+x < PAD.l + 18 || +x > W - PAD.r - 18) continue;
      const d = new Date(st.candles[i].t), day = d.getDate();
      const lab = st.tf.intraday && lastDay !== null && day !== lastDay ? fmtTime(st.candles[i].t, st.tf, true) : fmtTime(st.candles[i].t, st.tf);
      lastDay = day;
      parts.push(`<line class="grid v" x1="${x}" x2="${x}" y1="${PAD.t}" y2="${H - PAD.b}"/><text class="ax" text-anchor="middle" x="${x}" y="${H - 6}">${lab}</text>`);
    }
    parts.push(`<line class="axline" x1="${W - PAD.r}" x2="${W - PAD.r}" y1="${PAD.t}" y2="${H - PAD.b}"/>`);
    // ── 거래량
    if (g.showVol) {
      const bw = Math.max(1, cw * 0.62);
      parts.push(`<line class="grid" x1="${PAD.l}" x2="${W - PAD.r}" y1="${g.volTop - PAD.gap / 2}" y2="${g.volTop - PAD.gap / 2}"/><text class="ax dim" x="${W - PAD.r + 6}" y="${g.volTop + 9}">${volTxt(g.vmax)}</text>`);
      for (let i = st.vs; i < st.ve; i++) {
        const k = st.candles[i], x = g.x(i), y = g.yv(k.v);
        parts.push(`<rect class="vol ${k.c >= k.o ? "up" : "down"}" x="${(x - bw / 2).toFixed(1)}" y="${y.toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(0.5, g.volTop + g.volH - y).toFixed(1)}"/>`);
      }
    }
    // ── 캔들
    const bw = Math.max(1, Math.min(cw * 0.66, 18));
    for (let i = st.vs; i < st.ve; i++) {
      const k = st.candles[i], x = g.x(i), up = k.c >= k.o;
      const yo = g.y(k.o), yc = g.y(k.c), top = Math.min(yo, yc), hgt = Math.max(1, Math.abs(yo - yc));
      parts.push(`<line class="wick ${up ? "up" : "down"}" x1="${x.toFixed(1)}" x2="${x.toFixed(1)}" y1="${g.y(k.h).toFixed(1)}" y2="${g.y(k.l).toFixed(1)}"/>`);
      parts.push(`<rect class="body ${up ? "up" : "down"}" x="${(x - bw / 2).toFixed(1)}" y="${top.toFixed(1)}" width="${bw.toFixed(1)}" height="${hgt.toFixed(1)}"/>`);
    }
    // ── 이동평균
    for (const key of ["ma5", "ma20", "ma60"]) {
      if (!st.ind[key]) continue;
      const arr = st.mas[key]; let d = "", pen = false;
      for (let i = st.vs; i < st.ve; i++) { const m = arr?.[i]; if (m == null) { pen = false; continue; } d += `${pen ? "L" : "M"}${g.x(i).toFixed(1)} ${g.y(m).toFixed(1)}`; pen = true; }
      if (d) parts.push(`<path class="ma ${key}" d="${d}"/>`);
    }
    // ── 오버레이 라인(현재가·평단·조건/지정가 주문)
    for (const o of st.overlays) {
      if (o.price == null || !Number.isFinite(o.price)) continue;
      const col = o.color || "var(--muted)";
      if (o.price < g.lo || o.price > g.hi) {   // 화면 밖: 가장자리 핀
        if (!o.label) continue;
        const below = o.price < g.lo, txt = `${below ? "▼" : "▲"} ${o.label}`, lw = txt.length * 7 + 12;
        const lx = o.right ? W - PAD.r - lw - 4 : PAD.l + 4, ly = below ? PAD.t + g.priceH - 16 : PAD.t + 2;
        parts.push(`<rect class="lbl pin" x="${lx}" y="${ly}" width="${lw.toFixed(0)}" height="14" rx="2" fill="${col}" opacity="0.85"/><text class="lbltxt" x="${lx + 6}" y="${ly + 11}">${esc(txt)}</text>`);
        continue;
      }
      const y = g.y(o.price).toFixed(1);
      parts.push(`<line class="ov ${o.kind || ""}" x1="${PAD.l}" x2="${W - PAD.r}" y1="${y}" y2="${y}" stroke="${col}" stroke-dasharray="${o.dash || "5 4"}"/>`);
      const tagW = 62, ty = Math.max(PAD.t + 8, Math.min(H - PAD.b - 8, +y));
      parts.push(`<rect class="tag" x="${W - PAD.r + 2}" y="${ty - 8}" width="${tagW}" height="16" rx="2" fill="${col}"/><text class="tagtxt" x="${W - PAD.r + 2 + tagW / 2}" y="${ty + 4}" text-anchor="middle">${won(o.price)}</text>`);
      if (o.label) {
        const lw = o.label.length * 7.2 + 12;
        const lx = o.right ? W - PAD.r - lw - 4 : PAD.l + 4;
        parts.push(`<rect class="lbl" x="${lx}" y="${+y - 15}" width="${lw.toFixed(0)}" height="14" rx="2" fill="${col}"/><text class="lbltxt" x="${lx + 6}" y="${+y - 4}">${esc(o.label)}</text>`);
      }
    }
    gMain.innerHTML = parts.join("");
    drawOhlc(st.hover ?? st.candles.length - 1);
    if (st.hover != null) drawXh();
  }

  function drawOhlc(i) {
    const k = st.candles[i]; if (!k) { ohlcBox.innerHTML = ""; return; }
    const cls = k.c >= k.o ? "up" : "down";
    const prevC = st.candles[i - 1]?.c ?? k.o, d = k.c - prevC, r = prevC ? (100 * d / prevC).toFixed(2) : "0.00";
    const maTxt = ["ma5", "ma20", "ma60"].filter((m) => st.ind[m] && st.mas[m]?.[i] != null).map((m) => `<span class="${m}">${m.toUpperCase()} ${won(st.mas[m][i])}</span>`).join("");
    ohlcBox.innerHTML = `<span class="t">${fmtTime(k.t, st.tf, true)}</span><span>시 <b class="${cls}">${won(k.o)}</b></span><span>고 <b class="${cls}">${won(k.h)}</b></span><span>저 <b class="${cls}">${won(k.l)}</b></span><span>종 <b class="${cls}">${won(k.c)}</b></span><span class="${d > 0 ? "up" : d < 0 ? "down" : ""}">${d > 0 ? "▲" : d < 0 ? "▼" : ""}${won(Math.abs(d))} (${r}%)</span><span>거래량 ${won(k.v)}</span>${maTxt}`;
  }

  function drawXh() {
    const g = st.geo; if (!g || st.hover == null || !st.pendingMove) { gXh.style.display = "none"; return; }
    const { x: mx, y: my } = st.pendingMove;
    const i = st.hover, k = st.candles[i]; if (!k) return;
    const cx = g.x(i).toFixed(1);
    const yy = Math.max(PAD.t, Math.min(g.H - PAD.b, my));
    const inPrice = yy <= PAD.t + g.priceH;
    const val = inPrice ? g.yInv(yy) : null;
    const tW = 62, ttxt = fmtTime(k.t, st.tf, true), tw = ttxt.length * 6.6 + 10;
    gXh.style.display = "";
    gXh.innerHTML = `<line class="xh" x1="${cx}" x2="${cx}" y1="${PAD.t}" y2="${g.H - PAD.b}"/><line class="xh" x1="${PAD.l}" x2="${g.W - PAD.r}" y1="${yy.toFixed(1)}" y2="${yy.toFixed(1)}"/>`
      + (val != null ? `<rect class="xtag" x="${g.W - PAD.r + 2}" y="${(yy - 8).toFixed(1)}" width="${tW}" height="16" rx="2"/><text class="xtagtxt" x="${g.W - PAD.r + 2 + tW / 2}" y="${(yy + 4).toFixed(1)}" text-anchor="middle">${won(roundTick(val))}</text>` : "")
      + `<rect class="xtag" x="${(+cx - tw / 2).toFixed(1)}" y="${g.H - PAD.b + 2}" width="${tw.toFixed(0)}" height="16" rx="2"/><text class="xtagtxt" x="${cx}" y="${g.H - PAD.b + 14}" text-anchor="middle">${ttxt}</text>`;
    void mx;
  }

  // ── 마우스: 십자선(rAF 스로틀) · 휠 줌 · 드래그 팬
  const idxAt = (px) => { const g = st.geo; if (!g) return null; const i = Math.floor((px - PAD.l) / g.cw) + st.vs; return i >= st.vs && i < st.ve ? i : null; };
  function flushMove() {
    st.raf = 0; const m = st.pendingMove; if (!m) return;
    if (st.drag) {
      const g = st.geo, di = Math.round((st.drag.x - m.x) / g.cw);
      if (di) { const n = st.ve - st.vs; let vs = st.drag.vs + di; vs = Math.max(0, Math.min(st.candles.length - n, vs)); if (vs !== st.vs) { st.vs = vs; st.ve = vs + n; render(); } }
      return;
    }
    const i = idxAt(m.x);
    if (i !== st.hover) { st.hover = i; drawOhlc(i ?? st.candles.length - 1); }
    drawXh();
  }
  const onMove = (e) => { const r = host.getBoundingClientRect(); st.pendingMove = { x: e.clientX - r.left, y: e.clientY - r.top }; if (!st.raf) st.raf = requestAnimationFrame(flushMove); };
  const onLeave = () => { st.hover = null; st.pendingMove = null; st.drag = null; gXh.style.display = "none"; drawOhlc(st.candles.length - 1); host.classList.remove("dragging"); };
  const onWheel = (e) => {
    e.preventDefault(); if (!st.candles.length) return;
    const r = host.getBoundingClientRect(), px = e.clientX - r.left, g = st.geo;
    const n = st.ve - st.vs, total = st.candles.length;
    const factor = e.deltaY > 0 ? 1.18 : 1 / 1.18;
    const nn = Math.max(20, Math.min(total, Math.round(n * factor)));
    if (nn === n) return;
    const frac = Math.max(0, Math.min(1, (px - PAD.l) / (g.W - PAD.l - PAD.r)));
    const anchor = st.vs + frac * n;
    let vs = Math.round(anchor - frac * nn); vs = Math.max(0, Math.min(total - nn, vs));
    st.vs = vs; st.ve = vs + nn; render();
  };
  const onDown = (e) => { if (e.button !== 0) return; const r = host.getBoundingClientRect(); st.drag = { x: e.clientX - r.left, vs: st.vs }; host.classList.add("dragging"); gXh.style.display = "none"; };
  const onUp = () => { if (st.drag) { st.drag = null; host.classList.remove("dragging"); } };
  host.addEventListener("mousemove", onMove); host.addEventListener("mouseleave", onLeave);
  host.addEventListener("wheel", onWheel, { passive: false }); host.addEventListener("mousedown", onDown); window.addEventListener("mouseup", onUp);
  const ro = new ResizeObserver(() => render()); ro.observe(host);

  function recomputeMas() { st.mas = { ma5: ma(st.candles, 5), ma20: ma(st.candles, 20), ma60: ma(st.candles, 60) }; }
  return {
    setSeries(candles, tf) { st.candles = candles; st.tf = tf; recomputeMas(); const n = candles.length; const vis = Math.min(n, Math.max(60, Math.round(n * 0.62))); st.ve = n; st.vs = n - vis; st.hover = null; render(); },
    setLive(price) { const k = st.candles[st.candles.length - 1]; if (!k) return; k.c = price; if (price > k.h) k.h = price; if (price < k.l) k.l = price; recomputeMas(); render(); },
    setOverlays(list) { st.overlays = list || []; render(); },
    setIndicators(ind) { Object.assign(st.ind, ind); render(); },
    getIndicators() { return { ...st.ind }; },
    render,
    destroy() { ro.disconnect(); host.removeEventListener("mousemove", onMove); host.removeEventListener("mouseleave", onLeave); host.removeEventListener("wheel", onWheel); host.removeEventListener("mousedown", onDown); window.removeEventListener("mouseup", onUp); },
  };
}
