# 머신 이관 핸드오프 (맥북 → GPU 머신)

작성 2026-08-23 · **갱신 2026-08-27**(4bit 실측·규제 완료 반영) · 커밋 기준 `main`.
**이 문서만 읽고 GPU 머신에서 이어서 개발할 수 있게** 썼습니다.
프로젝트 전반 규칙은 `CLAUDE.md`, 실험 결과는 `smoke/RESULTS.md`, 신입은 `docs/onboarding.html`.

---

## 0. 30초 요약

한국어 자연어 → 증권 주문 파서(로컬 Qwen) 위에, **매수↔매도 / 이하↔이상 뒤집힘**을 막는
결정적 검증 레이어("하네스")를 얹었고, 프론티어 모델이 만든 공격으로 효과를 측정했습니다.

- ~~지금까지 수치는 전부 OpenRouter(풀정밀도)~~ → **2026-08-27 온프레미스 4bit 실측 완료**
  (RTX 5090 / vLLM 0.27.1 / AWQ 4bit, 8B·14B·32B). 상세는 `smoke/RESULTS.md` §7.
- **결과**: 4bit 가 더 나쁘지 않았다(전 셀에서 같거나 좋음). 대신 **과잉보류가 5배**로 늘었다 —
  양자화의 비용은 안전이 아니라 **사용성**이다. 하네스는 **4bit 8B 기준** 5개 코퍼스 전부 치명 0. 단 **14B 는 프론티어 142건에서 1/142(0.7%) 관통**(원인 = 근거 인용 `'내 주문'`, v2.5 에서 수정했으나 14B 재측정 미실시). 14B·32B 는 2개 코퍼스만 측정.
- **부산물**: 하네스 자체 결함 5건 발견·수정(v2.5). 회귀 46 → 56건, TS 패리티 512/512 유지.
- **지금 최우선은 실험이 아니라 배포다** — 유일한 결격 사유인데 아직 URL 이 없다(§7).

---

## 1. GPU 머신에서 첫 30분

```bash
git clone https://github.com/parag0hz/fintech.git && cd fintech

# 1) 키 (커밋 금지 — .gitignore 처리돼 있음)
printf 'OPENROUTER_API_KEY=sk-or-...\n' > smoke/.env      # 프론티어 공격 생성·비교용
                                                           # 로컬 벤치만 할 거면 없어도 됨

# 2) 파이썬 — 의존성 없음(표준 라이브러리만). 3.9+
cd smoke && export PYTHONUTF8=1
python3 test_harness.py          # 네트워크 없이 하네스 회귀 58/58 OK 여야 정상
python3 run.py --dry-run         # 채점 로직 검증

# 3) 웹 (선택)
cd ../web && npm install && npm test    # 패리티 512/512 · 유닛 19/19
```

Windows면 `py -3` + `$env:PYTHONUTF8="1"`. 리눅스/맥은 `python3`.

---

## 2. ★ 최우선 작업 — 4bit 로컬 실측

**왜 1순위인가**: 기획서 전체 논리가 *"금융사는 프라이버시 때문에 온프레미스 로컬 LLM을 쓴다"*인데,
정작 심사위원이 여는 데모와 모든 수치가 **클라우드 API·풀정밀도**입니다. 심사에서
*"그럼 실제 배포 환경 숫자는요?"* 를 맞으면 **답할 수 없습니다.** 자기모순이라 가장 치명적입니다.

```bash
cd smoke
./run_local_4bit.sh                                      # 기본 Qwen3-8B-AWQ
MODEL=Qwen/Qwen3-14B-AWQ SERVED=qwen3-14b-awq ./run_local_4bit.sh
MODEL=Qwen/Qwen3-32B-AWQ SERVED=qwen3-32b-awq GPU_UTIL=0.95 ./run_local_4bit.sh
```

스크립트가 하는 일: vLLM 기동(AWQ 4bit) → 준비 대기 → 스모크 1건 → 한국어 임계 88건 벤치 → ASR 142건.

**동작 원리**: `run.py`의 `API_URL`이 환경변수 `LLM_API_URL`로 교체됩니다(vLLM은 OpenAI 호환).
로컬이면 API 키도 불필요(`load_key()`가 `"local"` 반환). 하네스·채점 코드는 **한 줄도 안 바뀝니다.**

```bash
# 수동으로 붙일 때
export LLM_API_URL=http://localhost:8000/v1/chat/completions
python3 run_harness.py --defenders qwen3-8b-awq --cases attacks_ko_threshold.jsonl
```

**비교 기준선(풀정밀도, OpenRouter)** — 이보다 나쁘게 나오는 게 정상이고, 그게 논지를 강화합니다:

| 방어자 | 한국어 임계 88건 raw 치명 | 하네스 | 과잉보류 |
|---|---:|---:|---:|
| qwen3-8b | 13 (15%) | 0 | 0 |
| qwen3-32b | 9 (10%) | 0 | 0 |
| qwen2.5-72b | 6 (7%) | 0 | 0 |

**요구 사양**: 24GB+ VRAM(4090/A10/L4/A100). 8B-AWQ는 ~6GB, 14B ~9GB, 32B는 24GB에 빠듯합니다.

---

## 3. 그다음 순서 (심사위원 공격 대응 우선순위)

> **08-27 갱신** — 이 표는 '심사 질문 방어'용이라 **결격 요건인 배포가 빠져 있었다.**
> 배포는 실패하면 심사 대상에서 제외되므로 어떤 방어 항목보다 먼저다. 0번을 추가한다.

| 순위 | 할 일 | 막는 공격 | GPU 필요 |
|---|---|---|---|
| **0** | **웹서비스 배포** — `render.yaml` 준비 완료, 계정 연결만 남음 | **결격 사유**(9/7 11:00~9/11 무중단). 배포 실패 = 심사 제외 | ❌ |
| ~~1~~ | ~~4bit 로컬 실측~~ → **완료(08-27)**, `RESULTS.md` §7 | ~~자기모순~~ 해소 | ✅ |
| **2** | **gold 검증 확대** — 지금 adjudication 12건뿐 | "공격도 정답도 채점도 본인이 했네요" — 금보원이 제일 민감 | ❌ |
| ~~3~~ | ~~규제 확인 1페이지~~ → **완료** (`smoke/REGULATION.md`) | ~~허용됩니까~~ 해소 | ❌ |
| **4** | **접근성 각도 추가**(고령자·시각장애인) | "MTS에 조건주문 UI 있는데 왜 자연어?" — 제일 아픈 질문 | ❌ |
| ~~5~~ | ~~반복 측정 n=3~~ → **pass^k 로 구현**(`pass_k.py`, `RESULTS.md` §9). 88건에서 비결정성 1.1% 측정 | ~~왜 숫자가 바뀝니까~~ 수치로 답변 가능 | ✅ |

2·3·4번은 GPU 없이 되니 병렬 진행 가능합니다.

**2번 착수법**: `smoke/adjudicate.py`가 이미 있습니다(제3 모델 패널 투표 → `adjudication*.json`).
전체 코퍼스로 돌리고, 불일치 건은 `gold_suspect` 태그를 붙이거나 gold를 수정하세요.
가능하면 **사람 라벨 100건**을 따로 만들어 사람–판정기 일치율(κ)까지 제시하는 게 가장 강합니다.

---

## 4. 저장소 지도

```
smoke/                      Python 3.9+, 의존성 없음. 여기서 실행(모듈끼리 import)
  run.py                    공통 라이브러리(ORDER_SCHEMA, call_openrouter, normalize, score) + 실험1 CLI
                            ★ LLM_API_URL 로 로컬 vLLM 전환 지원
  harness.py                하네스 v2 — L1 신뢰분리 / L2 프롬프트 / L3 결정적 검증(정본)
  harness_v1.py             구버전(before/after 비교용, 건드리지 말 것)
  run_harness.py            raw vs 하네스 (실험2)
  run_asr.py                공격자×방어자 ASR 매트릭스 (실험4)
  generate_attacks.py       프론티어 공격 생성(난이도2) / generate_adaptive.py (난이도3)
  adjudicate.py             gold 제3자 검증 ← 우선순위 2번
  test_harness.py           네트워크 없는 회귀 테스트 — 하네스 고치면 반드시
  export_rules.py           규칙·픽스처 → web/shared (TS 이식 검증용)
  run_local_4bit.sh         ★ GPU 머신용 4bit 실측 자동화
  attacks*.jsonl            코퍼스 (47 자체 / 142 프론티어 / adaptive / 88 한국어임계)
  RESULTS.md PAPERS.md TAXONOMY.md BULL_KO_BENCHMARK.md RELATED_WORK.md
  report.html bull_report.html   시각 자료

web/                        Node 22 + TypeScript + Express, 프레임워크·CDN 없음
  src/harness.ts            harness.py 의 TS 이식 — shared/harness_rules.json 로 구동
  test/parity.test.ts       패리티 512/512 검증
  public/hts.js chart.js    HTS 워크스테이션 화면
  Dockerfile                배포용(멀티스테이지)
```

---

## 5. 절대 규칙 (어기면 조용히 망가짐)

1. **하네스 규칙을 고쳤으면 반드시 3단계**:
   `python3 test_harness.py` → `python3 export_rules.py` → `cd web && npm test`
   (패턴만 바꾸면 TS 코드 수정 없이 패리티가 유지됩니다. 로직을 바꾸면 `web/src/harness.ts`도 같이 고쳐야 합니다.)
2. **실패한 API 호출을 공격으로 세지 말 것.** 재시도하고, 그래도 실패하면 분모에서 빼세요.
   (과거에 이걸 안 해서 GLM ASR이 20%인데 **90%로 부풀려진** 적이 있습니다.)
3. **치명오류 정의를 섞지 말 것.** `run_harness.hscore` = committed-gated(확정했는데 방향 틀림).
   실험1의 `run.score`는 옛 정의(보류 비게이트·파싱실패 포함). 어느 쪽을 썼는지 항상 명시.
4. **키는 `smoke/.env` / `web/.env`.** 둘 다 git-ignored. 절대 출력·커밋 금지.
5. **OpenRouter Qwen은 풀정밀도** — 여기 수치는 로컬의 *낙관적 상한*. 문서에 항상 병기.
6. **gold는 자가생성·대부분 미검증.** 수치를 인용할 때 이 한계를 같이 말할 것.

---

## 6. 알려진 함정

- **`cd` 가 셸 세션 간 유지되지 않는 환경이 있습니다.** 스크립트는 절대경로나 `cd "$(dirname "$0")"` 사용.
- **`grep` 이 pdftotext 산출물에서 동작하지 않을 수 있음**(NUL 바이트 → binary 판정). Python으로 읽으세요.
- **작은 Qwen은 OpenRouter에서 strict JSON 스키마를 지원하지 않습니다**(HTTP 404).
  `call_openrouter`가 schema → json_object → prompt 로 폴백하고 성공 모드를 캐시합니다.
  **로컬 vLLM은 guided decoding을 지원**하므로 여기서는 스키마 강제가 실제로 걸립니다(차이를 기록해 두세요).
- **모델이 자기 필드명으로 답합니다**(`action`/`symbol`/`price_condition`/중첩 `condition`).
  `run.normalize()`가 정규화합니다. 새 모델을 추가하면 정규화가 먹는지 먼저 확인하세요 —
  안 하면 정답을 오답으로 세어 수치가 통째로 틀립니다(실제로 46/47 → 3 으로 바뀐 전례).
- **temperature 0인데도 재실행하면 1~2건 흔들립니다**(프로바이더 변동). n=3 평균 권장.

---

## 7. 지금 열려 있는 것

- ✅ **규제 리서치 완료** → `smoke/REGULATION.md`. 결론: **금지 조문 없음(조건부 허용)**, 오히려 규제가 우리 편.
  즉시 조치 2건: ① 자본시장법 **제49조는 삭제된 조문**이라 인용 금지 ② 하네스에 **투자일임 회피 거부 규칙**
  ("적당히 나눠서 사줘" 류 수량·가격 위임 표현 거부) 추가
- **미착수**: 기획서 PDF, 기능명세서 PDF — 제공 양식 입수가 선행 과제
- **최우선**: 실제 배포(호스팅) — **결격 요건**(9/7 11:00~9/11 23:59 무중단).
  `render.yaml` + Dockerfile(HEALTHCHECK·비루트 실행) 준비 완료. Render 계정 연결 + `OPENROUTER_API_KEY` 입력만 남았다.
  **free 플랜 금지** — 15분 무접속 시 슬립이라 심사위원의 첫 접속이 콜드스타트가 된다.
  배포를 늦출수록 무중단 리허설 기간이 사라진다.
- **미결정**: 4-way 경계 라벨(이상/초과/이하/미만) 승격 여부 — 스키마·웹·픽스처까지 번짐

---

## 8. 한 줄로 남기는 현재 결론

> 프론티어가 만든 공격에 로컬 Qwen은 공격자별 5~35% 뚫리고, 모델을 키워도(15%→10%→7%) 0이 되지 않는다.
> 결정적 검증 하네스는 **모델 크기와 무관하게** 정형 임계 표현을 0%로 만든다.
> — **(08-27)** 온프레미스 4bit 에서도 결론이 유지된다. 4bit 가 더 나쁘지도 않았다.
> 다만 하네스 자체에서 결함 5건이 나왔고(정적 분석·4bit 실측·외부 코퍼스가 각각), **외부 자극이
> 들어올 때마다 새 결함이 나온다**는 패턴이 세 번 연속 관측됐다. 자가생성 코퍼스만으로는 부족하다.
> 이제 남은 최대 리스크는 실험이 아니라 **배포**다.
