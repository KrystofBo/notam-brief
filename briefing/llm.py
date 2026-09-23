"""Model stage on Nebius Token Factory (OpenAI-compatible chat completions).

Each request carries the system prompt, the flight, the weather and a chunk of NOTAMs, and asks
for strict JSON: one item per NOTAM with relevant / priority / reason / summary.
"""
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

import requests

from . import config

SYSTEM_PROMPT = (config.PROMPTS / "system_prompt.md").read_text(encoding="utf-8")
PRIORITIES = ("HIGH", "MEDIUM", "LOW")


class LLMError(RuntimeError):
    pass


def schema(ids):
    """Output schema. The id enum and item count stop the model inventing or dropping NOTAMs."""
    item = {
        "type": "object",
        "properties": {
            "id": {"type": "string", "enum": list(ids)},
            "relevant": {"type": "boolean"},
            "priority": {"anyOf": [{"type": "string", "enum": list(PRIORITIES)}, {"type": "null"}]},
            "reason": {"type": "string"},
            "summary": {"type": "string"},
        },
        "required": ["id", "relevant", "priority", "reason", "summary"],
        "additionalProperties": False,
    }
    items = {"type": "array", "items": item, "minItems": len(ids), "maxItems": len(ids)} if ids else \
        {"type": "array", "maxItems": 0}
    return {"type": "object", "properties": {"weather_summary": {"type": "string"}, "items": items},
            "required": ["weather_summary", "items"], "additionalProperties": False}


def supports_reasoning(model):
    try:
        return "reasoning" in ((models_info().get(model) or {}).get("supported_features") or [])
    except Exception:
        return False


def chat(model, messages, response_format=None, max_tokens=32000, reasoning_effort=None):
    body = {"model": model, "messages": messages, "temperature": 0, "max_tokens": max_tokens}
    if response_format:
        body["response_format"] = response_format
    if reasoning_effort and supports_reasoning(model):
        body["reasoning_effort"] = reasoning_effort  # "none" turns DeepSeek's thinking off
    headers = {"Authorization": f"Bearer {config.api_key()}"}
    t0 = time.perf_counter()
    for attempt in range(6):
        try:
            r = requests.post(f"{config.NEBIUS_BASE_URL}/chat/completions", json=body, headers=headers, timeout=600)
        except requests.RequestException as e:
            raise LLMError(f"request failed: {e}") from e
        if r.status_code in (429, 502, 503, 504) and attempt < 5:
            wait = r.headers.get("Retry-After")
            time.sleep(float(wait) if wait and wait.replace(".", "", 1).isdigit() else 4 * 2 ** attempt)
            continue
        break
    if r.status_code >= 400:
        raise LLMError(f"HTTP {r.status_code}: {r.text[:400]}")
    data = r.json()
    choice = data["choices"][0]
    return {"content": choice["message"].get("content") or "", "finish": choice.get("finish_reason"),
            "usage": data.get("usage") or {}, "latency_s": time.perf_counter() - t0}


def parse_json(text):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        i, j = text.find("{"), text.rfind("}")
        if 0 <= i < j:
            return json.loads(text[i:j + 1])
        raise


def user_message(flight_block, weather_text, notams, weather_here=True):
    if not weather_here:
        wx = "(Weather is handled in a separate request. Return an empty weather_summary.)"
    else:
        wx = weather_text or "(no weather supplied)"
    body = "\n\n".join(n["raw"] for n in notams) or "(none)"
    return f"FLIGHT\n{flight_block}\n\nWEATHER\n{wx}\n\nNOTAMS ({len(notams)} items)\n{body}"


FORMAT_OK = {}  # model -> index into _formats() of the first response_format the model accepted


def _formats(ids):
    s = schema(ids)
    return [{"type": "json_schema", "json_schema": {"name": "briefing", "schema": s, "strict": True}},  # OpenAI style
            {"type": "json_schema", "json_schema": s},  # bare schema, as in the Token Factory docs
            {"type": "json_object"}]  # no schema support: the prompt carries the contract


def _chat_json(model, msgs, ids, reasoning_effort=None):
    fmts, err = _formats(ids), None
    for i in range(FORMAT_OK.get(model, 0), len(fmts)):
        try:
            res = chat(model, msgs, fmts[i], reasoning_effort=reasoning_effort)
        except LLMError as e:
            if not str(e).startswith(("HTTP 400", "HTTP 422")):
                raise
            err = e
            continue
        FORMAT_OK[model] = i
        return res
    raise err


def _assess_chunk(model, flight_block, weather_text, chunk, weather_here, reasoning_effort=None, depth=0):
    ids = [n["id"] for n in chunk]
    msgs = [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message(flight_block, weather_text, chunk, weather_here)}]
    res = _chat_json(model, msgs, ids, reasoning_effort)
    calls, errors = [res], []
    try:
        out = parse_json(res["content"])
    except (json.JSONDecodeError, ValueError):
        out = None
    if (out is None or res["finish"] == "length") and len(chunk) > 1 and depth < 3:
        # Truncated or unparseable: split the chunk and try again rather than losing NOTAMs.
        mid = len(chunk) // 2
        a = _assess_chunk(model, flight_block, weather_text, chunk[:mid], weather_here, reasoning_effort, depth + 1)
        b = _assess_chunk(model, flight_block, weather_text, chunk[mid:], False, reasoning_effort, depth + 1)
        return {"weather_summary": a["weather_summary"], "items": a["items"] + b["items"],
                "calls": calls + a["calls"] + b["calls"],
                "errors": [f"split chunk of {len(chunk)} after {'truncation' if out else 'invalid JSON'}"]
                + a["errors"] + b["errors"]}
    if out is None:
        errors.append(f"invalid JSON for {len(chunk)} NOTAMs")
        out = {}
    return {"weather_summary": str(out.get("weather_summary") or ""), "items": out.get("items") or [],
            "calls": calls, "errors": errors}


@lru_cache(maxsize=1)
def models_info():
    r = requests.get(f"{config.NEBIUS_BASE_URL}/models", params={"verbose": "true"},
                     headers={"Authorization": f"Bearer {config.api_key()}"}, timeout=30)
    r.raise_for_status()
    return {m["id"]: m for m in r.json().get("data", [])}


def price(model):
    """USD per 1M tokens (input, output)."""
    try:
        p = (models_info().get(model) or {}).get("pricing") or {}
        pin, pout = float(p.get("prompt") or 0), float(p.get("completion") or 0)
        if pin or pout:
            return pin * 1e6, pout * 1e6  # the API reports USD per token
    except Exception:
        pass
    return config.PRICES.get(model)


def assess(model, flight_block, weather_text, notams, chunk_size=80, workers=4, reasoning_effort=None):
    chunks = [notams[i:i + chunk_size] for i in range(0, len(notams), chunk_size)] or [[]]
    if not notams and not weather_text:
        chunks = []
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(chunks)))) as pool:
        parts = list(pool.map(lambda ic: _assess_chunk(model, flight_block, weather_text, ic[1], ic[0] == 0,
                                                       reasoning_effort),
                              enumerate(chunks)))
    latency = time.perf_counter() - t0

    wanted = {n["id"] for n in notams}
    by_id = {}
    for part in parts:
        for it in part["items"]:
            if isinstance(it, dict) and it.get("id") in wanted and it["id"] not in by_id:
                by_id[it["id"]] = it
    items = []
    for n in notams:
        it = by_id.get(n["id"])
        if it is None:
            items.append({"id": n["id"], "assessed": False, "relevant": None, "priority": None,
                          "reason": "The model did not return this NOTAM. Read the original.", "summary": ""})
            continue
        relevant = bool(it.get("relevant"))
        pri = str(it.get("priority") or "").upper()
        if relevant and pri not in PRIORITIES:
            pri = "LOW"  # relevant but unranked: keep it visible
        items.append({"id": n["id"], "assessed": True, "relevant": relevant, "priority": pri if relevant else None,
                      "reason": str(it.get("reason") or ""), "summary": str(it.get("summary") or "") if relevant else ""})

    calls = [c for p in parts for c in p["calls"]]
    usage = {"prompt_tokens": sum(c["usage"].get("prompt_tokens", 0) for c in calls),
             "completion_tokens": sum(c["usage"].get("completion_tokens", 0) for c in calls)}
    p = price(model)
    cost = (usage["prompt_tokens"] * p[0] + usage["completion_tokens"] * p[1]) / 1e6 if p else None
    return {"weather_summary": parts[0]["weather_summary"] if parts else "", "items": items, "usage": usage,
            "cost_usd": cost, "latency_s": latency, "calls": len(calls),
            "errors": [e for p_ in parts for e in p_["errors"]]}
