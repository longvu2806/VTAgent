#!/usr/bin/env bash
# Start Qdrant and two vLLM servers on the pod, then wait until all three answer.
# Every server listens on 127.0.0.1 only; reach them through an SSH tunnel if needed.
#
#   bash deploy/runpod/start.sh                       # qwen3.5-9b
#   LLM_MODEL=... LLM_MEMORY=0.75 bash deploy/runpod/start.sh   # another answer model
#
# Memory on a 24 GB card (RTX A5000): LLM ~62%, bge-m3 ~10%, and ~2 GB left for the
# onnxruntime reranker that runs inside the benchmark process.
set -euo pipefail

W="${WORKSPACE:-/workspace}"
LLM_MODEL="${LLM_MODEL:-Qwen/Qwen3.5-9B}"
LLM_MEMORY="${LLM_MEMORY:-0.62}"
EMBED_MEMORY="${EMBED_MEMORY:-0.10}"
MAX_LEN="${MAX_LEN:-16384}"  # prompt (~3k tokens) + thinking + answer
export HF_HOME="$W/hf"
mkdir -p "$W/logs"

wait_for() {  # name, url, log
  for _ in $(seq 1 180); do
    if curl -sf "$2" > /dev/null; then echo "$1 ready"; return 0; fi
    sleep 5
  done
  echo "$1 did not start; last lines of $3:"; tail -n 30 "$3"; exit 1
}

QDRANT__STORAGE__STORAGE_PATH="$W/qdrant/storage" QDRANT__SERVICE__HOST=127.0.0.1 \
  nohup "$W/qdrant/qdrant" > "$W/logs/qdrant.log" 2>&1 &
wait_for qdrant http://127.0.0.1:6333/readyz "$W/logs/qdrant.log"

# No official FP8 checkpoint: vLLM quantizes the weights to FP8 as it loads them (on Ampere a
# weight-only kernel). The qwen3 reasoning parser keeps the thinking out of the answer text;
# whether to think is chosen per request (VTAGENT_LLM_THINKING).
nohup "$W/venv-vllm/bin/vllm" serve "$LLM_MODEL" --host 127.0.0.1 --port 8001 \
  --quantization fp8 --gpu-memory-utilization "$LLM_MEMORY" --max-model-len "$MAX_LEN" \
  --reasoning-parser qwen3 > "$W/logs/vllm-llm.log" 2>&1 &
# One at a time: each vLLM sizes its cache from the memory free when it starts.
wait_for "vllm $LLM_MODEL" http://127.0.0.1:8001/health "$W/logs/vllm-llm.log"

nohup "$W/venv-vllm/bin/vllm" serve BAAI/bge-m3 --host 127.0.0.1 --port 8002 \
  --gpu-memory-utilization "$EMBED_MEMORY" > "$W/logs/vllm-embed.log" 2>&1 &
wait_for "vllm bge-m3" http://127.0.0.1:8002/health "$W/logs/vllm-embed.log"

nvidia-smi --query-gpu=memory.used,memory.total --format=csv
echo "servers up: run the benchmark with  bash deploy/runpod/bench.sh --limit 3"
