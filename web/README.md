# 자연어 주문 파싱 안전 하네스 — 웹 MVP

한국어 "텍스트 → 증권 주문" 파서 위에 얹는 안전 하네스(L1 문맥 신뢰 분리 · L2 강화 프롬프트 · L3 결정적 검증)의
데모/코퍼스/대시보드 웹입니다. `smoke/harness.py`(Python 정본)를 TypeScript 로 이식했고, 규칙과 패리티 픽스처는
`shared/harness_rules.json`, `shared/parity_fixture.json` 을 단일 소스로 사용합니다(하네스 v2.5 기준, 패리티 512/512).

- 프레임워크·번들러·CDN 없이 Node 22 + Express + 정적 ES 모듈 한 벌로 동작합니다.
- 화면: **주문(기본, `#/hts`)** — 데스크톱 HTS 워크스테이션 화면(다크 기본) + "분석" 그룹 3개: **파서 데모**(raw vs 하네스 비교, 단서 하이라이트, 플래그 설명) · **공격 코퍼스**(필터·검색·상세·방어자별 결과) · **결과 대시보드**(KPI, 실험1/2, ASR 매트릭스, mech×target 히트맵, 플래그 빈도).

## 주문 화면 (`#/hts`)

심사위원·비개발 팀원이 한 화면에서 제품을 이해하도록 만든 데모입니다: "말로 주문 → AI가 이해 → 하네스가 보낼 내용을 정확히 보여 주고 불확실하면 되묻기 → 하네스가 없었다면 어땠을지". 영웅문류 PC HTS 를 본뜬 **데스크톱 워크스테이션 레이아웃**(1440~1920 폭 기준, 100vh 안에 고정·페이지 스크롤 없음·패널 내부 스크롤, 12~13px, 다크 기본·라이트 토글)입니다. 1100px 이하에서는 패널을 세로로 쌓습니다.

스크린샷: `docs/screenshots/hts2_1920_initial.png`(1920×1080) · `hts2_1440_initial.png` · `hts2_1440_condorder.png`(조건부 매수 접수 → 차트 조건 라인 + 주문내역 '조건 대기') · `hts2_1440_abstain.png`(보류 카드) · `hts2_1440_crosshair.png`(십자선·OHLCV 판독).

- **제목줄**: 서비스명 · 모의계좌 000-00-000000 · 예수금 · KOSPI/KOSDAQ 모의 지수·등락 · 시계(HH:MM:SS) · 모델 선택 · 세션 초기화 · ☀/☾ 라이트·다크 토글(`localStorage.hts_ui_v2`, `html[data-theme]` 로 앱 전체에 적용). 상단 전역 내비(주문 | 분석: 파서 데모·공격 코퍼스·결과 대시보드)는 주문 화면에서 슬림하게 유지됩니다.
- **좌(268px) 관심종목**: 22종목 표(종목명·현재가·등락·등락률·거래량, 모의 시세: 상승 빨강/하락 파랑, 3초마다 결정적 난수 워크), 선택 행 하이라이트, 검색(별칭/코드, Enter 로 선택). 클릭하면 차트·호가창이 그 종목으로 바뀝니다.
- **중앙(≥55%) 차트 패널** (`public/chart.js`, 인라인 SVG): 머리(종목명·코드·현재가·전일대비·시/고/저·거래량·보유/평단/손익) · 타임프레임 [1분][10분][일][주][월] · 지표 토글 [MA5][MA20][MA60][거래량]. 종목코드+타임프레임으로 시드된 **결정적 모의 시계열**(150~200봉, 종목·타임프레임이 바뀔 때만 재생성, 마지막 봉만 실시간 갱신) 위에 캔들(양봉 빨강/음봉 파랑)·이동평균·거래량 서브패널(22%)·가격 격자·우측 가격축·하단 시간축(분봉은 09:00~15:30 장중만) · **십자선**(mousemove rAF 스로틀, OHLCV+MA 판독, 축 가격/시각 태그) · 휠 확대/축소·드래그 이동. **오버레이 라인**: 현재가(점선+태그), 보유 평단(회색 점선 "평단 250,000"), 이 세션의 미체결 지정가/조건부 주문마다 점선 + "조건 매수 260,000 이하"(빨강)/"조건 매도 …"(파랑) 라벨 — 화면 범위 밖이면 가장자리 핀(▲/▼)으로 표시.
- **우(≈26vw, 372~420px)**: 위 = **호가창 10단**(매도호가 10단 파랑·잔량 막대 왼쪽으로, 현재가 행, 매수호가 10단 빨강·막대 오른쪽으로, 등락률, 총잔량, 체결강도 모의) · 아래(≥45%) = **AI 주문 대화**(대화 로그·확인 카드·입력·마이크(Web Speech API ko-KR)·예시 7종 칩·머리줄에 뉴스 건수/비신뢰 전달 표시 + "인젝션 뉴스 수신(데모)" 버튼). 확인 카드는 1440×900 에서 내부 스크롤 없이 들어가도록 13px 로 압축했습니다.
- **하단 띠(200px, 좌+중앙 폭)**: 탭 [잔고] [주문내역] [체결내역] [뉴스·알림]. 주문내역 = 시각·주문번호·종목·구분(매수/매도 색)·수량·가격/조건·유형·상태(접수/조건 대기/체결/취소)·[취소]; 체결내역 = 체결된 주문; 뉴스·알림 = 뉴스 전체 목록(인젝션 항목은 "⚠ 지시문 포함 — 데이터로만 전달" 태그). 마지막 3건이 다음 파싱에 **비신뢰 context** 로 전달됩니다. 주문을 보내면 해당 탭(체결이면 체결내역, 아니면 주문내역)으로 자동 전환.
- 흐름: 발화 → `POST /api/parse` (history = 이 세션 주문의 구조화 dict 목록, context = 최근 뉴스) → **주문 확인 카드**(매수/매도 필, 종목·수량·주문유형·조건·예상 금액, "왜 이렇게 이해했나요?" 소비자 문장, "하네스 없이 AI만 썼다면?" 비교·경고 배너, 계좌 검사(보유 초과·예수금 초과)) → [주문 전송]/[수정]/[취소]. 보류(abstain)면 노란 카드로 구체적 질문 하나 + 빠른 답변 칩(원 발화 뒤에 붙여 재실행). 카드가 만들어지거나 주문을 보내면 그 종목으로 차트·호가창이 전환돼 조건 라인이 바로 보입니다.
- 전송하면 주문내역에 접수(시장가는 즉시 체결·잔고/예수금 반영, 조건부는 "조건 대기"), 세션 history 에 dict 로 추가됩니다. 취소하면 `cancelled: true` 로 남아 "아까 취소한 그거…" 흐름에 쓰입니다(이력에 주문이 2개 이상이면 하네스가 확인을 요청하는 것이 정상). 취소하면 차트의 조건 라인도 사라집니다.
- 세션(주문·대화·뉴스)은 localStorage(`hts_session_v1`)에 저장, "세션 초기화" 버튼으로 삭제. UI 설정(테마·타임프레임·지표·하단 탭)은 `hts_ui_v2`. 자동 실행 링크: `#/hts?reset=1&inject=1&raw=1&theme=light&tf=10m&say=발화`.
- 플래그→소비자 문장 매핑: `public/hts.js` 의 `consumerReason(flag, ctx)`; 보류 질문·칩: `questionFor(flags, vm)`; 카드 해석(수량 해석·계좌 검사·raw 비교): `interpret(msg)`; 차트 오버레이 목록: `overlays()`; 시계열/차트: `public/chart.js` 의 `makeSeries()` / `createChart()`.

### 예비 규칙 파서 (`src/fallback.ts`)

모델 응답이 없을 때(키 없음·호출 실패·비JSON) 화면이 막히지 않도록 발화에서 규칙으로 8필드를 채웁니다: 종목(6자리 코드 → 이름/별칭, `public/stocks.json`), 수량(`N주`), 금액(`N원어치`), 가격(`N만N천원`, 만/천 단위, 뒤에 에/이하/이상 등이 오는 수), 주문유형(시장가/현재가/호가 → MARKET, 가격 있으면 LIMIT), 방향/조건은 단서로만 채우고 최종 결정은 그대로 L3 `deterministicCheck` 가 합니다. 참조 표현("그거/방금/반대로")이 있고 구조화 이력이 있으면 직전 주문의 종목·수량·가격·유형을 승계합니다. 이때 응답에 `fallback: true` / `degraded: "no_key"|"llm_error"` 가 붙고 카드에 "예비 규칙 파서 사용(모델 응답 없음)" 이 표시됩니다.

## 실행

```bash
cd web
npm install
cp .env.example .env          # OPENROUTER_API_KEY 채우기 (없어도 규칙 미리보기·코퍼스·대시보드는 동작)
npm run dev                   # http://localhost:3000  (tsx watch)
```

프로덕션:

```bash
npm run build && npm start    # dist/server.js
```

데이터는 `SMOKE_DIR`(기본 `../smoke`)에서 읽고, 없으면 `web/data/` 를 사용합니다. 배포용으로 복사하려면:

```bash
npm run sync-data             # ../smoke → web/data/  (없는 파일은 건너뜀, snapshots/ 포함)
```

읽는 파일(있는 것만, 없으면 '데이터 없음'):
- 코퍼스 `attacks.jsonl`(자체작성) · `attacks_frontier9.jsonl`(프론티어) · `attacks_adaptive*.jsonl`(적응형 그룹 — adaptive2/adaptive3 등 추가 파일도 자동 포함) + `tags_<stem>.jsonl`(없으면 케이스 내장 target/mech 사용)
- 실험1 `results_full.json`, `results_q25.json`
- 실험2 `harness_results[_v1].json` + `harness_rows[_v1].json`
- ASR `asr_<stem>[_v1].json` + `asr_rows_<stem>[_v1].json` (stem = 코퍼스 파일 stem, 자동 탐지) · 레거시 `asr_8b/asr_32b.json`
- `snapshots/v2.0/*.json` 이 있으면 "v2.0"(패치 전 스냅샷) 열로 함께 표시

`.env` 는 `web/.env` → `SMOKE_DIR/.env` 순으로 읽습니다(이미 설정된 환경변수는 덮지 않음).

## 조건 주문의 의미 모델 (조건가 vs 주문가, 퍼센트 손익, OCO)

- **canonical 필드**: 하네스 최종 결과(`final`)는 기존 8필드에 더해 조건 주문일 때 `trigger_price`(조건이 발동되는 가격), `order_price`(발동 후 낼 지정가, 시장가면 null), 퍼센트 주문이면 `reference_price`/`reference_type`(`USER_PRICE`·`ENTRY_PRICE`·`AVG_PRICE`·`LAST_BUY_ORDER`), `loss_pct`/`gain_pct`, `exit_type`(`STOP_LOSS`/`TAKE_PROFIT`/`BUY_DIP`/`BUY_BREAKOUT`)를 갖습니다. 구 스키마 호환을 위해 `price` 는 조건 주문이면 조건가(트리거), 아니면 지정가를 담습니다(adapter 규칙).
- **퍼센트 손익**("손절은 -5%일때", "5% 빠지면 팔아", "매수가보다 3% 떨어지면 매도")은 문자열 치환이 아니라 L3 가 기준가를 찾아 절대 가격으로 환산합니다. 기준가 우선순위: 발화 명시 기준가 → 이 대화의 같은 종목 **매수 체결가**(`history[].fill_price`) → 계좌 포지션 **평균단가**(`positions[].avg_price`) → 이력의 마지막 매수 주문가. 현재가는 기준으로 쓰지 않으며, 기준가를 못 찾으면 `pct_no_reference→confirm` 으로 보류합니다. 매수 쪽 퍼센트("5% 빠지면 사")는 명시 기준가만 인정합니다.
- **스탑 주문 유형**: 퍼센트 손절/익절은 **스탑-마켓**(조건 발동 시 시장가, `order_type=MARKET`, `order_price=null`)으로 만듭니다. "257,450원 이하가 되면 손절"은 그 가격의 지정가 매도가 아니라 트리거이며, 급락 시 지정가 손절은 미체결될 수 있어 지정가를 임의로 넣지 않습니다. 스탑-리밋(발동 후 지정가)은 사용자가 지정가를 명시할 때만 — 현재는 표현을 지원하지 않아 TODO 입니다.
- **이력 carry-over 규칙**: L3 는 이력의 `price`/`condition` 을 새 주문에 복사하지 않습니다. 예외는 (a) '그거/반대로' 참조 시 조건 승계·반전, (b) 퍼센트 주문의 **기준가 조회**뿐입니다. 모델(raw)이 이전 주문의 272,000/GE 를 끌어와도 L3 가 재계산하며 `pct_overrode_model_cond→GE` 로 기록합니다.
- **목록 밖 표현(근거 인용)**: 하네스 프롬프트는 모델에게 방향 판단의 근거 단어를 발화에서 **그대로 인용**(`side_evidence`)하게 하고, L3 `verifyEvidence` 가 그 단어가 실제 발화에 있고 부정·정정·인용문 안이 아니며 방향 중립어(걸어/넣어/설정…)가 아닐 때만 인정합니다(`side_from_evidence→…`). 조건(LE/GE) 근거 인용은 실측에서 해로워 쓰지 않고, 방향어 없는 조건절은 실행 등가성(매도+GE ≡ 지정가 매도, 매수+LE ≡ 지정가 매수)으로 판단하며 스탑 방향(매도+LE·매수+GE)만 확인을 요청합니다. 매도 수량이 없으면 보유 수량으로 채웁니다(`qty_from_position`).
- **일상어체 **합성** 코퍼스(LLM 생성 문체 13종 — 실사용자 발화 아님)**: `smoke/attacks_phrasebook.jsonl`(240건, 반말·존댓말·은어·오타·장황·감정·방언·영어혼용·음성인식오류·조건부·퍼센트·참조) — `smoke/eval_phrasebook.py` 로 치명오류율·확인요청률을 잽니다.
- **주문 화면**: `POST /api/parse` 에 `history`(체결 주문은 `fill_price` 포함)와 `positions`(보유 종목·수량·평단)를 함께 보냅니다. 카드는 "조건 257,450원 이하가 되면 (매수 체결가 271,000원 대비 -5%)", "조건 발동 시 시장가", **트리거 기준 예상 금액 2,574,500원**(체결가는 달라질 수 있음)으로 표시합니다. 같은 종목의 매도 청산 조건(익절·손절)은 **OCO** 로 묶여(주문내역 `OCO` 표시) 모의 시세가 조건에 닿아 하나가 체결되면 나머지는 자동 취소됩니다. 실주문 연동 시에는 브로커의 스탑/OCO API 로 교체해야 합니다(TODO).

## 패리티 테스트

```bash
npm test
# [parity] 512/512 통과, 0 실패
# [unit] 19/19 통과
```

`test/parity.test.ts` 가 `shared/parity_fixture.json` 의 모든 항목에 대해 `deterministicCheck(utterance, history, parsed)` 의
`final`(키 순서 무관 deep-equal)과 `flags`(배열 정확 일치)를 검사하고, `normalize`/`korNum`/`sanitizeUntrusted`/`buildMessages`
단위 테스트를 함께 돌립니다. 하나라도 실패하면 exit code 1 입니다.

Python 쪽 규칙이 바뀌면 `py -3 smoke/export_rules.py` 로 `shared/*.json` 을 재생성한 뒤 `npm test` 를 다시 돌리면 됩니다
(정규식은 JSON 에서 읽어 컴파일하므로 대개 TS 수정 없이 통과합니다).

## 환경변수

| 이름 | 기본값 | 설명 |
|---|---|---|
| `OPENROUTER_API_KEY` | (없음) | 서버 전용. 없으면 `/api/parse` 는 예비 규칙 파서 + L3 로 동작(`degraded: "no_key"`) |
| `DEFENDER_MODEL` | `qwen/qwen3-8b` | 기본 방어자 모델 |
| `DAILY_CALL_CAP` | `500` | 프로세스 전체 일일 모델 호출 상한(파싱 1회 = raw+하네스 2콜) |
| `RATE_PER_MIN` | `20` | IP 당 분당 `/api/parse` 상한 |
| `LLM_TIMEOUT_MS` | `60000` | 모델 호출 타임아웃 |
| `PORT` | `3000` | 포트 |
| `SMOKE_DIR` | `../smoke` | 코퍼스·결과 파일 위치 (없으면 `./data`) |

## API

| 메서드/경로 | 설명 |
|---|---|
| `GET /api/health` | 상태, 키 유무, 모델 목록, 일일 사용량, 코퍼스 건수 |
| `POST /api/parse` | `{utterance, history?, context?, model?, flip_policy?}` → `{model, ms, raw:{pred,raw_json,mode,ms,err}, harness:{parsed,final,flags,detail,raw_json,mode,ms,err,fallback}, messages, raw_messages, degraded?, fallback?, warning?}`. raw 는 `run.py` 와 동일한 `[배경 정보]` 프롬프트(이력도 한 덩어리), 하네스는 `buildMessages`(L1+L2) → `normalize` → `deterministicCheck`(L3). 발화 ≤500자. 429 = 분당/일일 상한. 키 없음/모델 실패 시에도 200 으로 예비 규칙 파서 결과(`degraded`, `fallback:true`, `preview:true`)를 돌려줍니다 |
| `GET /api/stocks` | 관심종목·별칭 목록(`public/stocks.json`) |
| `GET /api/analyze?utterance=&history=` | 모델 없이 L3 단서 분석만(하이라이트용 start/end 포함) + 빈 주문 기준 미리보기 플래그 |
| `GET /api/corpus?file=attacks\|frontier9\|adaptive` | 코퍼스 + 태그(TAXONOMY) 조인 |
| `GET /api/case/:id` | 케이스 + 모든 결과 파일(실험1 raw, 실험2 v1/v2, ASR v1/v2, 적응형)에서 모은 방어자별 결과 |
| `GET /api/results` | 대시보드용 집계: KPI, 실험1 요약, 실험2 raw→v1→(v2.0)→v2, ASR 매트릭스(stem별 × 버전, 레거시), mech×target 히트맵(rows+tags 에서 재계산, 없으면 집계 파일의 heat), 플래그 빈도. `sources` 에 어떤 파일을 읽었는지 나열 |

파서 데모는 공유 링크를 지원합니다: `#/parse?u=발화&h=이력&c=문맥&m=모델&run=1`.

## 배포 (Render 예시)

1. 저장소 루트에서 `cd web && npm run sync-data` 로 `web/data/` 를 채우고 커밋합니다(컨테이너는 `../smoke` 를 볼 수 없습니다).
2. Render → New Web Service → 저장소 연결, **Root Directory** `web`, Runtime **Docker**(`web/Dockerfile`).
   - 또는 Node 런타임: Build `npm ci && npm run build`, Start `npm start`.
3. Environment 에 `OPENROUTER_API_KEY`, `DAILY_CALL_CAP`(예: 300), `SMOKE_DIR=./data` 를 넣습니다. `PORT` 는 Render 가 주입합니다.
4. 배포 후 `/api/health` 로 키·데이터 인식 여부를 확인합니다.

Railway/Fly 도 동일하게 `web/Dockerfile` 을 쓰면 됩니다(`fly launch --dockerfile web/Dockerfile`, 포트 3000).

## 구조

```
web/
  package.json  tsconfig.json  .env.example  Dockerfile  README.md
  shared/harness_rules.json      # L3 정규식·프롬프트 (export_rules.py 산출, 읽기 전용)
  shared/parity_fixture.json     # 패리티 픽스처 512건
  src/harness.ts                 # L1 sanitizeUntrusted · L2 buildMessages · L3 analyzeUtterance/historyOrder/deterministicCheck
  src/normalize.ts               # run.py normalize/_kor_num/_extract_json/SYS/ORDER_SCHEMA 이식
  src/openrouter.ts              # OpenRouter 호출 사다리(schema→json_object→prompt, /no_think, temperature 0)
  src/fallback.ts     예비 규칙 파서(모델 응답 없을 때)
  src/data.ts                    # 코퍼스·결과 로더(mtime 캐시) + 대시보드 집계
  src/server.ts                  # Express API + 정적 UI, 호출 제한
  scripts/sync-data.mjs          # ../smoke → data/ 복사
  test/parity.test.ts            # npm test
  public/index.html app.js style.css   # 라우터 + 분석 화면
  public/hts.js hts.css chart.js stocks.json   # 주문(HTS 워크스테이션) 화면 · SVG 캔들 차트 · 관심종목/별칭
  docs/screenshots/              # hts2_*.png (워크스테이션) · hts_*.png (이전 MTS 레이아웃)
  data/                          # sync-data 산출(배포용 사본)
```

## 이식 시 주의한 점

- Python `re` 와 JS `RegExp` 의 유니코드 차이: Python 의 `\b`/`\d` 는 유니코드(한글도 `\w`) 기준이라 `\b[sS][eE][lL][lL]\b` 가
  "삼성sell" 에 매치되지 않지만 JS 는 ASCII 기준으로 매치합니다. `harness.ts` 의 `pyRegex()` 가 `u` 플래그를 켜고
  `\b`→유니코드 경계 lookaround, `\d`→`\p{Nd}` 로 치환해 Python 의미를 재현합니다(u 모드가 거부하는 `\"` 같은
  identity escape 도 정리). 픽스처 외에 245개 발화의 전체 분석 결과(단서 위치 포함)와 338개 모델 출력의 `normalize` 결과를
  Python 과 대조해 불일치 0 을 확인했습니다.
- `normalize` 는 dict/list 를 `_kor_num` 에 넣었을 때 Python `str()` 표현에서 숫자를 뽑는 경로까지 재현합니다(`pyStr`).
- `history_order` 의 시스템 응답 접두(`history_system_prefix`)는 Python `re.match` 와 같게 문자열 시작에만 적용(`^` 부착), 취소/철회(`history_cancel`)는 `search`.
- 문자열 인덱스는 UTF-16 코드유닛 기준(브라우저 하이라이트와 일치). 한글·BMP 범위에서는 Python 과 동일하고,
  이모지 등 보조평면 문자가 섞이면 위치값만 다를 수 있습니다.
