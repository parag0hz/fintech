# text-to-order 안전 하네스

**2026 금융 AI Challenge** 출품작 (주최 금융보안원 · 운영 데이콘)

한국어 자연어를 증권 주문으로 바꾸는 **로컬 LLM 파서** 위에, 되돌릴 수 없는
**매수↔매도 · 이하↔이상 뒤집힘**을 막는 **결정적 검증 레이어("하네스")** 를 얹었다.

> AI가 공격당해서가 아니다. 평범한 말에도 되돌릴 수 없는 주문 오류가 나고,
> 어떤 모델도 완벽하지 않다 → 모델과 무관한 결정적 검증 레이어가 필수다.
> 그 레이어도 공격당하므로 **"모르면 확정하지 않는다"** 가 유일한 안전한 기본값이다.

---

## 왜 필요한가

- 증권사는 개인정보·망분리 때문에 **온프레미스 로컬 LLM**(Qwen 계열)을 써야 한다.
- "26만원 **이하**"가 "이상"으로 한 글자만 뒤집혀도 되돌릴 수 없다
  (KRX 착오매매 구제는 10% 초과 이탈만 대상).
- 금융투자협회 「금융사고 방지를 위한 모범규준」 제2-22조는 **매수·매도 주문 화면의
  색상과 형태를 다르게** 하라고 요구한다. 대화창에는 그 화면이 없다 — 하네스가 그 대체물이다.

## 핵심 결과

온프레미스 4bit AWQ 실측 (RTX 5090 / vLLM), 치명오류 = 확정했는데 방향·조건이 정답과 다름:

| 코퍼스 | raw (하네스 없음) | **하네스** |
|---|---|---|
| 프론티어 공격 142건 | 21.1% | **0.0%** |
| 한국어 임계 88건 | 8.0% | **0** |
| AgentDojo 파생 72건 | 23.6% | **0** |
| 보류 판단 30건 | 33.3% | **0** |

- **모델 크기로는 해결되지 않는다** — 풀정밀도에서 15%→10%→7%로 줄지만 0이 안 되고,
  프론티어 천장(Opus 5)도 47건 중 3건 틀린다.
- **규칙을 아는 적응형 공격**은 v2.0을 13%, v2.1을 18% 뚫었다. 확정 대신 확인 요청으로
  바꾸자 3라운드에서 3%로 수렴했다. 대가는 적대 입력에서 확인 요청률 ~40%(정상 2~4%).
- **양자화는 안전이 아니라 사용성을 깎는다** — 4bit에서 치명오류는 여전히 0이지만
  되묻는 횟수가 풀정밀도 대비 5배로 늘었다.

수치 출처는 [`smoke/RESULTS.md`](smoke/RESULTS.md), 실험 설계는 [`smoke/TAXONOMY.md`](smoke/TAXONOMY.md).

## 저장소 구조

```
smoke/     Python 3.9+ · 의존성 없음(표준 라이브러리만). 실험·하네스·코퍼스·결과
  harness.py            하네스 정본 — L1 신뢰분리 / L2 프롬프트 / L3 결정적 검증
  run_harness.py        raw vs 하네스 비교        run_asr.py   공격자×방어자 ASR
  pass_k.py             pass^k 신뢰성(k회 전부 안전한 비율)
  test_harness.py       회귀 테스트 — 하네스를 고치면 반드시 실행
  run_local_4bit.sh     온프레미스 4bit 실측 자동화(vLLM)
  attacks_*.jsonl       코퍼스 720건 (전부 자체 생성 — 대회가 데이터를 주지 않는다)

web/       Node 22 + TypeScript + Express · 프레임워크/CDN 없음. 대회 제출용 MVP
  src/harness.ts        harness.py 의 TS 이식 — shared/harness_rules.json 으로 구동
  test/parity.test.ts   Python↔TS 100% 동작 일치 검증(픽스처 512건)
  public/               HTS 워크스테이션 · 파서 데모 · 공격 코퍼스 · 결과 대시보드
```

## 빠른 시작

**요구 사항**: Python 3.9+ (의존성 없음) · **Node 22+** (웹) · GPU는 4bit 실측에만 필요

```bash
# 1) 하네스 회귀 테스트 — 네트워크 불필요, 여기서 OK 가 나와야 정상
cd smoke && PYTHONUTF8=1 python3 test_harness.py

# 2) 웹 데모 (빌드가 선행되어야 한다 — npm start 만으로는 dist/ 가 없어 실패한다)
cd web && npm install && npm run build && npm start
#    → http://localhost:3000 · 상태 확인: curl localhost:3000/api/health
#    API 키가 없어도 예비 규칙 파서로 동작한다(degraded 모드).

# 3) Python↔TS 패리티
cd web && npm test        # [parity] 512/512 · [unit] 19/19

# 4) 온프레미스 4bit 실측 (GPU 24GB+)
cd smoke && ./run_local_4bit.sh          # 기본 Qwen3-8B-AWQ
MODEL=Qwen/Qwen3-32B-AWQ SERVED=qwen3-32b-awq ./run_local_4bit.sh
```

## 하네스를 고칠 때 (반드시 3단계)

```bash
cd smoke
PYTHONUTF8=1 python3 test_harness.py     # 1. 회귀
PYTHONUTF8=1 python3 export_rules.py     # 2. 규칙·픽스처 재생성 → web/shared 로 전파
cd ../web && npm test                    # 3. TS 패리티
```

정규식만 바꾸면 TS 코드 수정 없이 패리티가 유지된다. **로직을 바꾸면
`web/src/harness.ts` 도 같이 고쳐야 한다.**

## 알아둘 것

- **API 키**: `smoke/.env` · `web/.env` 에 `OPENROUTER_API_KEY`. 둘 다 git-ignored. 출력·커밋 금지.
- **실패한 API 호출을 공격으로 세지 않는다.** 기록은 하되 분모에서 뺀다(`n_scored`).
- **치명오류 정의가 둘이다.** `run_harness.hscore`(committed-gated, 정본) vs
  실험1의 `run.score`(구정의). 인용할 때 어느 쪽인지 항상 명시할 것.
- **gold 는 자가생성이고 대부분 미검증이다.** 수치를 인용할 때 이 한계를 같이 말한다.

자세한 규칙은 [`CLAUDE.md`](CLAUDE.md), 이관·현황은 [`HANDOFF.md`](HANDOFF.md),
신입 안내는 [`docs/onboarding.html`](docs/onboarding.html).
