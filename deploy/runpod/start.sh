#!/usr/bin/env bash
# Start Qdrant and two vLLM servers on the pod, then wait until all three answer.
# Every server listens on 127.0.0.1 only; reach them through an SSH tunnel if needed.
#
#   bash deploy/runpod/start.sh                       # qwen3.5-9b
#   LLM_MODEL=... LLM_MEMORY=0.75 bash deploy/runpod/start.sh   # another answer model
#
# Memory on a 24 GB card (RTX A5000): LLM ~70% (FP8 weights ~10.7 GB, the rest cache),
# bge-m3 ~10%, and ~4 GB left for the onnxruntime reranker inside the benchmark process.
set -euo pipefail

W="${WORKSPACE:-/workspace}"
LLM_MODEL="${LLM_MODEL:-Qwen/Qwen3.5-9B}"
LLM_MEMORY="${LLM_MEMORY:-0.70}"
EMBED_MEMORY="${EMBED_MEMORY:-0.10}"
MAX_LEN="${MAX_LEN:-16384}"  # prompt (~3k tokens) + thinking + answer
# Requests decoded at once. Qwen3.5's linear-attention layers need one cache block per
# sequence, and vLLM's default of 256 does not fit in 24 GB.
MAX_SEQS="${MAX_SEQS:-32}"
export HF_HOME="$W/hf"
mkdir -p "$W/logs"

wait_for() {  # name, url, log; the server is the last background process
  local pid=$!
  for _ in $(seq 1 180); do
    if ! kill -0 "$pid" 2> /dev/null; then break; fi
    if curl -sf "$2" > /dev/null; then echo "$1 ready"; return 0; fi
    sleep 5
  done
  echo "$1 did not start; last lines of $3:"; tail -n 30 "$3"; exit 1
}

QDRANT__STORAGE__STORAGE_PATH="$W/qdrant/storage" QDRANT__SERVICE__HOST=127.0.0.1 \
  nohup "$W/qdrant/qdrant" > "$W/logs/qdrant.log" 2>&1 &
wait_for qdrant http://127.0.0.1:6333/readyz "$W/logs/qdrant.log"

# Ports: RunPod's own nginx holds 8001 (and 3001, 7270, 7861, 8081, 8888, 9091) on its images.

# No official FP8 checkpoint: vLLM quantizes the weights to FP8 as it loads them (on Ampere a
# weight-only kernel). The qwen3 reasoning parser keeps the thinking out of the answer text;
# whether to think is chosen per request (VTAGENT_LLM_THINKING). A request's thinking_token_budget
# (VTAGENT_LLM_THINKING_BUDGET) ends the thinking with REASONING_END, Qwen's own wording for a cut.
REASONING_END='\n\nConsidering the limited time by the user, I have to give the solution based on the thinking directly now.\n</think>\n\n'
nohup "$W/venv-vllm/bin/vllm" serve "$LLM_MODEL" --host 127.0.0.1 --port 8000 \
  --quantization fp8 --gpu-memory-utilization "$LLM_MEMORY" --max-model-len "$MAX_LEN" \
  --max-num-seqs "$MAX_SEQS" --reasoning-parser qwen3 \
  --reasoning-config "{\"reasoning_start_str\": \"<think>\", \"reasoning_end_str\": \"$REASONING_END\"}" \
  > "$W/logs/vllm-llm.log" 2>&1 &
# One at a time: each vLLM sizes its cache from the memory free when it starts.
wait_for "vllm $LLM_MODEL" http://127.0.0.1:8000/health "$W/logs/vllm-llm.log"

nohup "$W/venv-vllm/bin/vllm" serve BAAI/bge-m3 --host 127.0.0.1 --port 8002 \
  --gpu-memory-utilization "$EMBED_MEMORY" > "$W/logs/vllm-embed.log" 2>&1 &
wait_for "vllm bge-m3" http://127.0.0.1:8002/health "$W/logs/vllm-embed.log"

nvidia-smi --query-gpu=memory.used,memory.total --format=csv
echo "servers up: run the benchmark with  bash deploy/runpod/bench.sh --limit 3"
