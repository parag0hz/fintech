#!/usr/bin/env bash
# 온프레미스 4bit 양자화 실측 — GPU 머신에서 실행.
#
# 왜: 지금까지 수치는 전부 OpenRouter(풀정밀도)라, 우리 주장의 핵심 전제인
#     "증권사는 온프레미스 4bit로 돌린다" 환경에서는 한 번도 측정된 적이 없다.
#     심사에서 "그럼 실제 배포 환경 숫자는요?" 를 맞으면 답할 수 없다. 그걸 메운다.
#
# 요구: NVIDIA GPU 24GB+ (RTX 4090 / A10 / L4 / A100), CUDA 12.x, Python 3.10+
# 예상: 모델당 다운로드 5~20분 + 벤치 10~20분. 총 1~2시간.
set -euo pipefail
cd "$(dirname "$0")"

MODEL="${MODEL:-Qwen/Qwen3-8B-AWQ}"     # 4bit AWQ 공식 체크포인트
SERVED="${SERVED:-qwen3-8b-awq}"        # --model 인자로 쓸 별칭
PORT="${PORT:-8000}"
GPU_UTIL="${GPU_UTIL:-0.90}"
MAXLEN="${MAXLEN:-8192}"

echo "▶ 1/5  환경 확인"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || { echo "!! GPU 없음"; exit 1; }
python3 -c "import vllm" 2>/dev/null || { echo "▶ vLLM 설치"; pip install -q "vllm>=0.8.4"; }

# ── 실측에서 실제로 막혔던 환경 문제 3가지 (RTX 5090 / CUDA 13 / Python 3.13 기준) ──
# (1) nvcc 부재: 드라이버만 있고 시스템 CUDA 툴킷이 없으면 vLLM 의 JIT 커널 컴파일이 실패한다.
#     pip 로 들어온 nvidia-cuda-nvcc 를 CUDA_HOME 으로 잡아주면 해결된다.
if ! command -v nvcc >/dev/null 2>&1; then
  CU=$(python3 -c "import os,nvidia,glob;b=os.path.dirname(nvidia.__file__);c=glob.glob(b+'/cu*');print(c[0] if c else '')" 2>/dev/null || true)
  if [ -n "${CU:-}" ] && [ -x "$CU/bin/nvcc" ]; then
    export CUDA_HOME="$CU"; export PATH="$CUDA_HOME/bin:$PATH"
    export LD_LIBRARY_PATH="$CUDA_HOME/lib:${LD_LIBRARY_PATH:-}"
    echo "   CUDA_HOME=$CUDA_HOME (pip nvidia-cuda-nvcc)"
  fi
fi
# (2) ninja 부재: venv 의 python 을 직접 호출하면 venv/bin 이 PATH 에 없어 ninja 를 못 찾는다.
VENV_BIN=$(python3 -c "import sys,os;print(os.path.dirname(sys.executable))")
case ":$PATH:" in *":$VENV_BIN:"*) ;; *) export PATH="$VENV_BIN:$PATH";; esac
# (3) flashinfer JIT 헤더 충돌: flashinfer 가 번들한 CCCL 헤더와 nvcc 13.x 툴킷 헤더가 충돌해
#     "CUDA compiler and CUDA toolkit headers are incompatible" 로 기동이 깨진다.
#     어텐션은 FLASH_ATTN 을 쓰므로 샘플러만 끄면 된다.
export VLLM_USE_FLASHINFER_SAMPLER="${VLLM_USE_FLASHINFER_SAMPLER:-0}"
export VLLM_ATTENTION_BACKEND="${VLLM_ATTENTION_BACKEND:-FLASH_ATTN}"
# 벤치는 수백 콜 규모라 처리량보다 기동 안정성이 중요하다 → 컴파일/그래프 캡처 생략
EAGER="${EAGER:---enforce-eager}"
# 로컬 eager 는 지연이 커 기본 90초 타임아웃으로는 제외가 늘어난다(run.py 가 이 값을 읽는다)
export LLM_TIMEOUT="${LLM_TIMEOUT:-300}"

echo "▶ 2/5  vLLM 서버 기동 ($MODEL, AWQ 4bit)"
# 이전 실행의 vLLM 이 남아 있으면 GPU 메모리를 붙들고 있어 새 서버가 기동에 실패한다
# ("Free memory on device cuda:0 (11.18/31.36 GiB) is less than desired ..."). 실제로 이 때문에
# 벤치 전체가 전 호출 실패로 끝난 적이 있다. 종료시킨 뒤 메모리가 실제로 해제될 때까지 기다린다.
if pgrep -f "vllm[.]entrypoints" >/dev/null 2>&1; then
  echo "   기존 vLLM 종료 후 메모리 해제 대기"
  pkill -f "vllm[.]entrypoints" 2>/dev/null || true
fi
NEED=$(python3 -c "print(int($GPU_UTIL*$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits)))")
for i in $(seq 1 40); do
  FREE=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits)
  [ "$FREE" -ge "$NEED" ] && { echo "   ✓ 여유 ${FREE}MiB (필요 ${NEED}MiB)"; break; }
  [ "$i" = 40 ] && { echo "!! GPU 메모리 부족: 여유 ${FREE}MiB < 필요 ${NEED}MiB — GPU_UTIL 을 낮추거나 점유 프로세스를 정리하세요"; nvidia-smi; exit 1; }
  sleep 3
done

python3 -m vllm.entrypoints.openai.api_server \
  --model "$MODEL" --served-model-name "$SERVED" \
  --quantization awq --max-model-len "$MAXLEN" $EAGER \
  --gpu-memory-utilization "$GPU_UTIL" --port "$PORT" \
  > vllm_"$SERVED".log 2>&1 &
VLLM_PID=$!
trap 'kill $VLLM_PID 2>/dev/null || true' EXIT

echo "   서버 준비 대기(최대 20분, 첫 실행은 모델 다운로드 포함)"
for i in $(seq 1 240); do
  if curl -s "http://localhost:$PORT/v1/models" >/dev/null 2>&1; then echo "   ✓ 준비됨"; break; fi
  sleep 5
  [ "$i" = 240 ] && { echo "!! 기동 실패 — vllm_$SERVED.log 확인"; tail -30 vllm_"$SERVED".log; exit 1; }
done

export LLM_API_URL="http://localhost:$PORT/v1/chat/completions"
export PYTHONUTF8=1

echo "▶ 3/5  스모크 (1건) — 응답 형태 확인"
python3 - <<PY
import os, json
from run import call_openrouter, normalize, load_key
raw, usage = call_openrouter("$SERVED", None, "삼성전자 26만원 이하로 오면 100주 매수", load_key())
print("   mode:", usage.get("_mode"), "| 파싱:", {k: normalize(raw).get(k) for k in ("side","condition","price","quantity")})
PY

echo "▶ 4/5  벤치 — 한국어 임계 88건 (raw vs 하네스)"
python3 run_harness.py --defenders "$SERVED" --cases attacks_ko_threshold.jsonl \
  --out "harness_ko_local_$SERVED.json" --rows-out "harness_rows_ko_local_$SERVED.json" --workers 4

echo "▶ 5/5  벤치 — 프론티어 공격 142건 (ASR)"
python3 run_asr.py --attacks attacks_frontier9.jsonl --defenders "$SERVED" \
  --out "asr_local_$SERVED.json" --rows-out "asr_rows_local_$SERVED.json" \
  || echo "   (run_asr 옵션이 다르면 run_harness 결과만 써도 됨)"

echo
echo "✅ 완료. 결과 파일:"
ls -1 harness_ko_local_"$SERVED".json asr_local_"$SERVED".json 2>/dev/null || true
echo
echo "비교 (풀정밀도 OpenRouter 기준선):"
echo "  qwen3-8b   한국어임계 88건  raw 13(15%) → 하네스 0,  과잉보류 0"
echo "  → 로컬 4bit 수치가 이보다 나쁘면 그게 논지를 강화한다(양자화가 안전성을 깎는다)."
echo
echo "다음 모델도 재려면:"
echo "  MODEL=Qwen/Qwen3-14B-AWQ SERVED=qwen3-14b-awq ./run_local_4bit.sh"
echo "  MODEL=Qwen/Qwen3-32B-AWQ SERVED=qwen3-32b-awq ./run_local_4bit.sh   # 24GB 빠듯, GPU_UTIL=0.95"
