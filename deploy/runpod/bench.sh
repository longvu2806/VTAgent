#!/usr/bin/env bash
# Benchmark the answer model without and with thinking, R4 configuration, through the vLLM
# servers of start.sh. Extra arguments go to tests.eval.generate; a run resumes where it
# stopped, so a trial with --limit 3 counts towards the full run.
#
#   bash deploy/runpod/bench.sh --limit 3     # trial: 3 questions each
#   bash deploy/runpod/bench.sh               # all questions, then results.tgz to download
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
W="${WORKSPACE:-/workspace}"
DATASET="${DATASET:-data/test/luat_gtdb_2008_eval100.csv}"
PREFIX="${PREFIX:-a5000_9b}"
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
export VTAGENT_COLLECTION="${COLLECTION:-vtagent_docs_r3}"
export VTAGENT_CHUNKING=structured
export VTAGENT_SPARSE=bm25
export VTAGENT_RERANK=true
export VTAGENT_RERANK_DEVICE=cuda
export VTAGENT_RERANKER_FILE=onnx/model_fp16.onnx
export VTAGENT_PROMPT=v2

for thinking in false true; do
  name="$PREFIX"
  if [ "$thinking" = true ]; then name="${PREFIX}_think"; fi
  VTAGENT_LLM_THINKING=$thinking "$W/venv-app/bin/python" -m tests.eval.generate "$DATASET" --name "$name" "$@"
done

tar -czf "$W/results.tgz" -C data "eval_runs/$PREFIX" "eval_runs/${PREFIX}_think"
echo "results: $W/results.tgz (download it, then score on the laptop)"
