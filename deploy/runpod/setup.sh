#!/usr/bin/env bash
# One-time setup of a RunPod GPU pod for VTAgent benchmarks (SDD AD-10).
# Everything goes under $WORKSPACE (default /workspace), so a network volume keeps the
# environments and the models between pods; running it again only fills what is missing.
#
#   bash deploy/runpod/setup.sh
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
W="${WORKSPACE:-/workspace}"
VLLM_VERSION=0.34.0
ORT_VERSION=1.30.0       # same as onnxruntime in requirements.txt, GPU build
QDRANT_VERSION=v1.19.0   # in step with qdrant-client in requirements.txt
LLM_MODEL="${LLM_MODEL:-Qwen/Qwen3.5-9B}"
export HF_HOME="$W/hf"

python3 -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ needed: pick a py3.11+ pod template"'

# vLLM gets its own environment: it pins torch, transformers and numpy versions of its own.
if [ ! -x "$W/venv-vllm/bin/vllm" ]; then
  python3 -m venv "$W/venv-vllm"
  "$W/venv-vllm/bin/pip" install -q --upgrade pip
  "$W/venv-vllm/bin/pip" install -q "vllm==$VLLM_VERSION"
fi

# VTAgent itself, with the GPU build of onnxruntime for the reranker.
if [ ! -x "$W/venv-app/bin/python" ]; then
  python3 -m venv "$W/venv-app"
  "$W/venv-app/bin/pip" install -q --upgrade pip
  "$W/venv-app/bin/pip" install -q -r "$REPO/requirements.txt"
  "$W/venv-app/bin/pip" uninstall -y -q onnxruntime
  "$W/venv-app/bin/pip" install -q "onnxruntime-gpu[cuda,cudnn]==$ORT_VERSION"
fi

# Qdrant server binary (no Docker inside a pod).
if [ ! -x "$W/qdrant/qdrant" ]; then
  mkdir -p "$W/qdrant"
  curl -fsSL "https://github.com/qdrant/qdrant/releases/download/$QDRANT_VERSION/qdrant-x86_64-unknown-linux-gnu.tar.gz" \
    | tar -xz -C "$W/qdrant"
fi

# Models, downloaded once into $HF_HOME: the answer model, bge-m3 (embeddings and the
# chunking tokenizer) and the fp16 reranker for the GPU.
"$W/venv-app/bin/python" - "$LLM_MODEL" <<'PY'
import sys
from huggingface_hub import hf_hub_download, snapshot_download

snapshot_download(sys.argv[1])
snapshot_download("BAAI/bge-m3")
for name in ("onnx/model_fp16.onnx", "tokenizer.json"):
    hf_hub_download("onnx-community/bge-reranker-v2-m3-ONNX", name)
PY

echo "setup done: start the servers with  bash deploy/runpod/start.sh"
