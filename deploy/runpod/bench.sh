#!/usr/bin/env bash
# Benchmark the answer model without and with thinking, R4 configuration, through the vLLM
# servers of start.sh. Extra arguments go to tests.eval.generate; a run resumes where it
# stopped, so a trial with --limit 3 counts towards the full run.
#
#   bash deploy/runpod/bench.sh --limit 3     # trial: 3 questions each
#   bash deploy/runpod/bench.sh               # all questions, then results.tgz to download
#   HEADERS=true MODES=false PREFIX=a5000_9b_r2 bash deploy/runpod/bench.sh   # R4 + R2 headers, no thinking
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
W="${WORKSPACE:-/workspace}"
DATASET="${DATASET:-data/test/luat_gtdb_2008_eval100.csv}"
PREFIX="${PREFIX:-a5000_9b}"
HEADERS="${HEADERS:-false}"  # R2 contextual headers; built into their own collection
MODES="${MODES:-false true}"  # thinking off, then on
export HF_HOME="$W/hf"
cd "$REPO"

if [ ! -f "$DATASET" ]; then
  echo "$DATASET not found: copy data/test/ from the laptop first (data/ is not in git)"; exit 1
fi

# R4 (SAD Table 6.5) with prompt v2, models served by vLLM, reranker on the GPU.
export VTAGENT_MODEL_SERVER=openai
export VTAGENT_LLM_MODEL="${LLM_MODEL:-Qwen/Qwen3.5-9B}"
export VTAGENT_EMBEDDING_MODEL=BAAI/bge-m3
export VTAGENT_QDRANT_URL=http://127.0.0.1:6333
if [ "$HEADERS" = true ]; then DEFAULT_COLLECTION=vtagent_docs_r3_headers; else DEFAULT_COLLECTION=vtagent_docs_r3; fi
export VTAGENT_COLLECTION="${COLLECTION:-$DEFAULT_COLLECTION}"
export VTAGENT_CONTEXTUAL_HEADERS="$HEADERS"
export VTAGENT_CHUNKING=structured
export VTAGENT_SPARSE=bm25
export VTAGENT_RERANK=true
export VTAGENT_RERANK_DEVICE=cuda
export VTAGENT_RERANKER_FILE=onnx/model_fp16.onnx
export VTAGENT_PROMPT=v2

runs=()
for thinking in $MODES; do
  name="$PREFIX"
  if [ "$thinking" = true ]; then name="${PREFIX}_think"; fi
  VTAGENT_LLM_THINKING=$thinking "$W/venv-app/bin/python" -m tests.eval.generate "$DATASET" --name "$name" "$@"
  runs+=("eval_runs/$name")
done

tar -czf "$W/results.tgz" -C data "${runs[@]}"
echo "results: $W/results.tgz (download it, then score on the laptop)"
