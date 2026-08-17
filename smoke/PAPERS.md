# 참고 논문 — NL→주문 검증 & 로컬 LLM 하네스 (검증된 목록)

각 항목은 arXiv/venue를 실제 확인함. ⭐ = 필독 코어. 대회 맥락(금융보안원) 관련은 🇰🇷 표시.

---

## ⭐ 먼저 읽을 코어 8편

| 논문 | id | 왜 |
|---|---|---|
| ⭐ Can LLMs Effectively Process and Execute Financial Trading Instructions? (Kang et al., FITEE 2025) | 2412.04856 | **이 프로젝트 그 자체.** NL→구조화 주문 파이프라인. 프론티어조차 필드정확도 5~10%, 누락률 14~67%. "naive 파싱은 안전하지 않다"의 결정적 외부 증거. 단, 중국어·500건·검증기 없음 → 우리 빈칸. |
| ⭐ GBV-SQL: SQL2Text Back-Translation Validation (Chen et al., 2025) | 2509.12612 | 생성된 결과를 자연어로 **역번역해 원의도와 대조**하는 검증 에이전트 = 하네스 왕복검증의 학술 원형. BIRD +5.8%p. |
| ⭐ TrustSQL: Reliability with Penalty-Based Scoring (Lee et al., 2024) | 2403.15879 | 실행가능하면 정답, 불가능하면 **abstain**, 확신 오답은 무겁게 벌점 — 우리 "치명오류≫보류" 채점의 원형. |
| ⭐🇰🇷 Compliance-to-Code (Li et al., 2025) | 2505.19804 | 규정을 subject/condition/constraint로 분해해 **실행 가능한 Python으로 컴파일** = 하네스 L3(이하/이상 문자-그대로 결정적 강제)와 같은 "규칙을 LLM 밖 검증 로직으로" 패턴. |
| ⭐ Defending Indirect Injection with Spotlighting (Hines/MS, 2024) | 2403.14720 | 검색 문맥을 **데이터로 표시·격리**해 인젝션 성공률을 ~0%로 — 하네스 L1(비신뢰 문맥 격리)의 가장 가까운 선례. |
| ⭐ Increased LLM Vulnerabilities from Fine-tuning and Quantization (Kumar et al., 2024) | 2404.04392 | **Qwen을 직접 평가** — 파인튜닝·과도한 양자화가 안전정렬을 벗겨 탈옥 쉬워짐. "온프레미스 4bit Qwen이 취약하다"의 실증 근거. |
| ⭐🇰🇷 FinGuard: Financial Regulatory Non-Compliance Detection (Dou et al., 2026) | 2605.29427 | **Qwen3-8B 기반 가드 모델**로 규제 위반 탐지 + FinGuard-Bench. 우리 하네스와 거의 같은 아키텍처 → 직접 비교/차별화 대상. |
| ⭐ Scaling Trends in LM Robustness (Howe et al., ICML 2025) | 2407.18213 | "격차는 실재": 명시적 안전훈련 없으면 큰 모델도 일관되게 강건하지 않고, **공격 컴퓨트가 방어를 앞선다.** 작은 로컬이 왜 뚫리는지. |

---

## A. 도메인: NL→주문 파싱 & 금융 text-to-SQL

- 🔑 **Kang et al., FITEE 2025** — 2412.04856 (위 코어)
- **FinSQL / BULL benchmark** (Zhang et al., SIGMOD 2024) — 2401.10506 · 금융 특화 튜닝이 일반 Spider/BIRD를 능가(+36.6%). "일반 도구는 금융 의미를 놓친다."
- **BookSQL** (Kumar et al., NAACL 2024) — 2406.07860 · 회계 도메인 100k쌍, GPT-4도 큰 격차. "도메인셋을 직접 만든다"는 우리 플레이북.
- **FINCH** (Singh et al., 2025) — 2510.01887 · **조항 가중 채점(FINCH Score)** — 일반 exact-match가 금융 치명오류를 가린다는 우리 논리와 동일.
- (대조군, 결정≠파싱) FinMem 2311.13743 · FinAgent 2402.18485 · TradingAgents 2412.20138 · INVESTORBENCH 2412.18174 · BizFinBench 2505.19457
- **빈칸 노트:** NL→주문 파싱을 안전-검증 관점으로 다룬 논문은 사실상 Kang 하나뿐(검증기 없음). **한국어 × 주문 × 매수/매도·이하/이상 치명오류 검증기 = 열린 영역.** 이게 우리 신규성 근거.

## B. 검증 하네스 설계 (text-to-SQL 신뢰성)

- **CHASE-SQL** (Pourreza et al., ICLR 2025) — 2410.01943 · 다중후보 생성 + 학습된 pairwise 선택기(=주문 후보 선택기 이식 가능).
- **XiYan-SQL** (Liu et al., TKDE 2025) — 2507.04701 · 스타일 다른 생성기 앙상블 + 선택 모델.
- **LEVER** (Ni et al., ICML 2023) — 2302.08468 · **실행 결과로 후보를 검증·재랭크**하는 크리틱. Spider 포함 +4.6~10.9%.
- ⭐ **LLMs Cannot Self-Correct Reasoning Yet** (Huang et al., ICLR 2024) — 2310.01798 · **외부 피드백 없는 자기수정은 실패/악화** → "모델 자체 재확인" 말고 외부 검증기 근거.
- **Let's Verify Step by Step** (Lightman et al., 2023) — 2305.20050 · 최종 직렬화 말고 **중간 슬롯(side/qty/price)을 단계별 검증**.
- **Self-Consistency** (Wang et al., ICLR 2023) — 2203.11171 · 다중 샘플 일치 = 가장 값싼 검증층.

## C. 프롬프트 인젝션 방어 (하네스 L1 = 문맥 격리)

- ⭐ **Greshake et al. — Not what you've signed up for** (2023) — 2302.12173 · **간접 인젝션의 원조** — 검색된 뉴스/공시에 심긴 지시가 앱을 탈취. 우리 위협모델 그 자체.
- ⭐ **Spotlighting** (Hines/MS, 2024) — 2403.14720 (코어)
- **StruQ** (Chen et al., USENIX Sec 2025) — 2402.06363 · 프롬프트/데이터 채널 분리.
- **The Instruction Hierarchy** (Wallace/OpenAI, 2024) — 2404.13208 · system>user>content 우선순위 = "공시 텍스트는 주문 스펙을 못 이긴다".
- **SecAlign** (Chen et al., CCS 2025) — 2410.05451 · 인젝션 무시를 선호최적화로 학습(하네스를 파인튜닝할 경우).
- ⭐ **Can LLMs Separate Instructions from Data?** (Zverev et al., ICLR 2025) — 2403.06833 · **현 LLM은 지시/데이터를 못 가른다**는 형식적 증거 → 외부 격리층이 필요한 이유.
- **벤치마크(하네스 테스트용):** InjecAgent 2403.02691 · BIPIA 2312.14197 · **AgentDojo** 2406.13352 (주문 태스크 추가해 L1 검증 가능) · Formalizing/Known-Answer 2310.12815 · Tensor Trust 2311.01011 · OWASP LLM01:2025.

## D. 공격자=프론티어 & 격차는 실재 (레드팀 + 강건성)

- **Red Teaming LMs with LMs** (Perez et al., EMNLP 2022) — 2202.03286 · **LM이 LM을 레드팀**하는 방법론의 원조.
- **PAIR** 2310.08419 · **TAP** 2312.02119 · **Rainbow Teaming** 2402.16822 · AutoDAN 2310.04451 · GCG 2307.15043 — 공격자-LLM 자동화(우리 프론티어 공격 생성의 학술 대응). Rainbow은 **다양성 + 그 데이터로 방어 강화**까지.
- ⭐ **Scaling Trends in LM Robustness** (코어) — 2407.18213
- 🔑 **Increased Vulnerabilities from Fine-tuning & Quantization** (코어, Qwen 평가) — 2404.04392
- **Catastrophic Jailbreak via Decoding** (Huang et al., ICLR 2024) — 2310.06987 · 오픈모델은 디코딩 파라미터만 바꿔도 >95% 뚫림(온프레미스 운영자가 디코딩 제어 = 넓은 공격면).
- **Investigating Quantization on Safety** 2502.15799 · **Exploiting LLM Quantization** (NeurIPS 2024) 2405.18137 · **Weak-to-Strong Jailbreaking** (ICML 2024) 2401.17256.
- ⭐ **The Attacker Moves Second** (Nasr, Carlini, Tramèr et al., 2025) — 2510.09023 · 최근 방어 12종이 적응형 공격에 >90% 뚫림 → **하네스는 정적 아닌 적응형으로 스트레스테스트해야** 함(우리 다음 단계 근거).
- **측정 프로토콜:** HarmBench 2402.04249 · JailbreakBench 2404.01318 (raw vs 하네스 ASR 보고 표준).

## E. Abstention + 정직한 채점 (하네스 보류 + 측정 신뢰도)

- **Know Your Limits: Abstention Survey** (Wen et al., TACL 2024) — 2407.18418 · 보류의 정석 서베이.
- **R-Tuning: Say "I Don't Know"** (Zhang et al., NAACL 2024) — 2311.09677 · 로컬 모델을 "모르면 보류"로 튜닝.
- **LMs (Mostly) Know What They Know** (Kadavath et al., 2022) — 2207.05221 · P(IK) 자기지식 보정.
- ⭐ **StrongREJECT for Empty Jailbreaks** (Souly et al., NeurIPS 2024) — 2402.10260 · **순진한 채점기가 ASR을 부풀린다** → 내가 잡은 "90% 환상" 버그와 정확히 같은 교훈.
- **Judge 편향(gold adjudication 근거):** Self-Preference Bias 2410.21819 · LLM Evaluators Favor Own Generations 2404.13076 · Preference Leakage (ICLR 2026) 2502.01534 · MT-Bench 2306.05685 → **공격자와 판정자 계열을 분리하라**.
- **가드 프레임워크:** NeMo Guardrails 2310.10501 · Llama Guard 2312.06674 · Building Guardrails (ICML 2024) 2402.01822.

## F. 🇰🇷 한국 금융 + 대회 맥락 (금융보안원)

- ⭐ **FinGuard (Qwen3-8B 가드)** — 2605.29427 (코어)
- 🔑 **FinRED: 금융 LLM 레드팀** (Kim et al., 2026) — 2606.19887 · **금융보안원에 배포**되어 규제 AI 보안 테스트에 사용. 심사기관의 본업 — 인용해 "보완물"로 포지셔닝.
- **FinSafetyBench** (Hou et al., ACL 2026) — 2605.00706 · 이중언어 금융 레드팀(14개 위반 범주).
- **CoRT + FinRisk-Bench** (Cheng et al., ACL 2026) — 2509.10546 · 다중턴 위험은닉 공격, ASR 93~95%.
- **RAHS: 위험가중 harm 점수** (Dimino et al., 2026) — 2603.10807 · 치명오류(매수/매도·이하/이상)를 양성 실패보다 크게 가중.
- **LogiSafetyBench** (Song et al., 2026) — 2601.08196 · 큰 모델일수록 과제완수 위해 암묵 규제를 무시 → 외부 결정적 강제 근거.
- **한국 금융 평가 스택:** ₩on/Won-Instruct 2503.17963 · KFinEval-Pilot(금융 toxicity 축) 2504.13216 · KMMLU 2402.11548 · KMMLU-Pro 2507.08924 · TWICE/KorFinMTEB 2502.07131 · HRET 2503.22968 · KorFinASC 2301.03136.
- **FinBen** (Xie et al., NeurIPS 2024) — 2402.12659 · 금융 LLM 벤치마크의 기초 앵커.
