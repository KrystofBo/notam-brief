"""Paths, model settings and API key loading."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CACHE = Path("/tmp/notam-cache") if os.environ.get("VERCEL") else DATA / "cache"  # Vercel: only /tmp is writable
SNAPSHOTS = DATA / "snapshots"
PROMPTS = ROOT / "prompts"
EVAL = ROOT / "eval"

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*a, **k):
        return False
load_dotenv(ROOT / ".env")

NEBIUS_BASE_URL = os.environ.get("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1").rstrip("/")
MODAL_BASE_URL = os.environ.get("MODAL_BASE_URL", "https://inference.us-west.modal.direct/v1").rstrip("/")
DEFAULT_MODEL = os.environ.get("BRIEFING_MODEL", "deepseek-ai/DeepSeek-V4-Flash-0731")
# Sent as reasoning_effort to models that support it. "none" turns thinking off (about 4x fewer output
# tokens and much faster); "default" leaves the model's own reasoning on.
REASONING_EFFORT = os.environ.get("BRIEFING_REASONING_EFFORT", "none")

# USD per 1M tokens (input, output). Token Factory prices come from /v1/models when it reports them;
# Modal Shared Endpoint prices are from the Modal Library pages (Sep 2026; cached input is cheaper).
PRICES = {
    "deepseek-ai/DeepSeek-V4-Flash-0731": (0.14, 0.28),
    "modal:deepseek-ai/DeepSeek-V4.1-Flash": (0.30, 1.20),
    "modal:moonshotai/Kimi-K3": (3.00, 15.00),
}


def env(name):
    """A setting from the environment, .env (which may have been edited after start-up) or, on Windows, the
    user environment (`setx` only reaches new processes)."""
    if not os.environ.get(name):
        load_dotenv(ROOT / ".env")
    val = os.environ.get(name)
    if not val and os.name == "nt":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                val = winreg.QueryValueEx(k, name)[0]
        except OSError:
            val = None
    if not val:
        raise RuntimeError(f"{name} is not set. Add it to .env or your environment.")
    return val


def api_key():
    return env("NEBIUS_API_KEY")


def split_model(model):
    """'modal:Qwen/Qwen3-...' -> ('modal', 'Qwen/Qwen3-...'). A bare id is a Token Factory model."""
    head, sep, rest = model.partition(":")
    return (head, rest) if sep and "/" not in head else ("nebius", model)


def endpoint(provider):
    """(OpenAI-compatible base URL ending in /v1, auth headers) for a provider."""
    if provider == "nebius":
        return NEBIUS_BASE_URL, {"Authorization": f"Bearer {api_key()}"}
    if provider == "modal":
        # Modal Shared Endpoints (managed, per token). Create one per model in the dashboard's Endpoints tab;
        # requests carry a workspace proxy token as "Bearer wk-<id>.ws-<secret>".
        key, secret = env("MODAL_KEY"), env("MODAL_SECRET")
        return MODAL_BASE_URL, {"Authorization": f"Bearer {key}.{secret}"}
    raise ValueError(f"Unknown provider {provider!r}")
