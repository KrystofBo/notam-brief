"""Paths, model settings and API key loading."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CACHE = DATA / "cache"
SNAPSHOTS = DATA / "snapshots"
PROMPTS = ROOT / "prompts"
EVAL = ROOT / "eval"

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

NEBIUS_BASE_URL = os.environ.get("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1").rstrip("/")
DEFAULT_MODEL = os.environ.get("BRIEFING_MODEL", "deepseek-ai/DeepSeek-V4-Flash-0731")

# USD per 1M tokens (input, output). Used when /v1/models does not report pricing.
PRICES = {
    "deepseek-ai/DeepSeek-V4-Flash-0731": (0.14, 0.28),
}


def api_key():
    key = os.environ.get("NEBIUS_API_KEY")
    if not key and os.name == "nt":
        # `setx` only reaches new processes; read the user environment directly.
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                key = winreg.QueryValueEx(k, "NEBIUS_API_KEY")[0]
        except OSError:
            key = None
    if not key:
        raise RuntimeError("NEBIUS_API_KEY is not set. Add it to .env or your environment.")
    return key
