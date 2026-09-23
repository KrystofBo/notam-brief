"""Qwen3-30B-A3B-Instruct-2507 (FP8) behind vLLM's OpenAI-compatible server on one Modal H100.

The same model (also FP8) is on Nebius Token Factory, so this gives a like-for-like latency comparison.

    modal deploy modal_app/vllm_qwen.py      # prints the endpoint URL; put it in .env as MODAL_BASE_URL
    modal app stop notam-brief-vllm          # stop paying for the GPU

The endpoint requires Modal proxy auth: every request needs the Modal-Key / Modal-Secret headers
(MODAL_KEY / MODAL_SECRET in .env). The container shuts down after 5 idle minutes.
"""
import subprocess

import modal

MODEL = "Qwen/Qwen3-30B-A3B-Instruct-2507-FP8"
SERVED_AS = "Qwen/Qwen3-30B-A3B-Instruct-2507"  # same id as on Token Factory
PORT = 8000
MINUTES = 60

image = (
    modal.Image.from_registry("nvidia/cuda:12.9.0-devel-ubuntu22.04", add_python="3.12")
    .entrypoint([])
    .uv_pip_install("vllm==0.21.0")
    .env({"HF_XET_HIGH_PERFORMANCE": "1"})
)
hf_cache = modal.Volume.from_name("huggingface-cache", create_if_missing=True)
vllm_cache = modal.Volume.from_name("vllm-cache", create_if_missing=True)

app = modal.App("notam-brief-vllm")


@app.function(
    image=image,
    gpu="H100",
    scaledown_window=5 * MINUTES,
    timeout=10 * MINUTES,
    volumes={"/root/.cache/huggingface": hf_cache, "/root/.cache/vllm": vllm_cache},
)
@modal.concurrent(max_inputs=32)
@modal.web_server(port=PORT, startup_timeout=20 * MINUTES, requires_proxy_auth=True)
def serve():
    subprocess.Popen([
        "vllm", "serve", MODEL,
        "--served-model-name", SERVED_AS,
        "--host", "0.0.0.0", "--port", str(PORT),
        "--max-model-len", "65536",  # prompts reach ~10k tokens and the client reserves up to 32k for output
        "--gpu-memory-utilization", "0.90",
        "--uvicorn-log-level", "info",
    ])
