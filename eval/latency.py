"""Latency of the same briefing requests on Nebius Token Factory and on our own Modal deployment.

    python -m eval.latency --models deepseek-ai/DeepSeek-V4-Flash-0731 Qwen/Qwen3-30B-A3B-Instruct-2507 \
        modal:Qwen/Qwen3-30B-A3B-Instruct-2507 --repeat 2

Every request is streamed to record time to first token (TTFT), total time and decode speed. Requests are
interleaved across models, so load changes over time hit every model equally. The first request to each model
is reported separately: for Modal it includes a cold start if no container is warm. The briefing requests are
the real model-stage requests for the five labelled routes (snapshot, pre-filter on, no weather).

Writes eval/results/latency.md and eval/results/latency.csv.
"""
import argparse
import csv
import json
import statistics
import time
from datetime import datetime, timezone

import requests

from briefing import config, ingest, llm, prefilter
from briefing.pipeline import eval_routes, flight_block, make_flight

MODAL_GPU_USD_PER_S = 0.001097  # one H100 on Modal (modal.com/pricing, Sep 2026)
PING = [{"role": "user", "content": "Reply with the single word OK."}]


def stream(model, messages, response_format=None, max_tokens=16000):
    url, headers, body = llm.request_body(model, messages, response_format, max_tokens, config.REASONING_EFFORT)
    body.update(stream=True, stream_options={"include_usage": True})
    t0 = time.perf_counter()
    ttft, usage, parts = None, {}, []
    with requests.post(url, json=body, headers=headers, stream=True, timeout=1500) as r:
        if r.status_code >= 400:
            raise llm.LLMError(f"HTTP {r.status_code}: {r.text[:300]}")
        for line in r.iter_lines():
            if not line.startswith(b"data:"):
                continue
            data = line[5:].strip()
            if data == b"[DONE]":
                break
            d = json.loads(data)
            usage = d.get("usage") or usage
            for ch in d.get("choices") or []:
                delta = ch.get("delta") or {}
                if delta.get("content") or delta.get("reasoning_content"):
                    if ttft is None:
                        ttft = time.perf_counter() - t0
                    parts.append(delta.get("content") or "")
    total = time.perf_counter() - t0
    out = usage.get("completion_tokens")
    return {"ttft": ttft, "total": total, "tokens_in": usage.get("prompt_tokens"), "tokens_out": out,
            "decode_tps": (out - 1) / (total - ttft) if out and ttft is not None and total > ttft else None,
            "text": "".join(parts)}


def briefing_requests():
    cfg = eval_routes()
    notams = ingest.load(cfg["snapshot"])[0]
    reqs = []
    for r in cfg["routes"]:
        f = make_flight(r["dep"], r["dest"], path=r["path"], window=cfg["window"], alt_ft=cfg["alt_ft"],
                        band_fl=tuple(cfg["band_fl"]), corridor_nm=cfg["corridor_nm"])
        cands = prefilter.candidates(notams, f)
        msgs = [{"role": "system", "content": llm.SYSTEM_PROMPT},
                {"role": "user", "content": llm.user_message(flight_block(f, r.get("note")), "", cands)}]
        ids = [n["id"] for n in cands]
        reqs.append((r["id"], msgs, llm._formats(ids)[0], ids))
    return reqs


def complete(text, ids):
    """Did the answer parse and cover every NOTAM exactly once?"""
    try:
        items = llm.parse_json(text).get("items") or []
    except Exception:
        return False
    return sorted(i.get("id") for i in items if isinstance(i, dict)) == sorted(ids)


def cost(model, s):
    if config.split_model(model)[0] == "modal":
        return s["total"] * MODAL_GPU_USD_PER_S  # GPU-seconds, if the GPU served nothing else meanwhile
    p = llm.price(model)
    return (s["tokens_in"] * p[0] + s["tokens_out"] * p[1]) / 1e6 if p and s["tokens_in"] is not None else None


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def p95(xs):
    xs = sorted(x for x in xs if x is not None)
    return xs[round(0.95 * (len(xs) - 1))] if xs else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", nargs="+", required=True, help="Token Factory ids; prefix 'modal:' for our Modal endpoint")
    ap.add_argument("--repeat", type=int, default=2, help="rounds over the five briefing requests")
    ap.add_argument("--pings", type=int, default=3, help="tiny requests per round (time to first token floor)")
    a = ap.parse_args()

    reqs = briefing_requests()
    rows = []

    def record(kind, model, route, s, ok=None):
        rows.append({"kind": kind, "model": model, "route": route, "ttft": s["ttft"], "total": s["total"],
                     "tokens_in": s["tokens_in"], "tokens_out": s["tokens_out"], "decode_tps": s["decode_tps"],
                     "complete": ok, "cost_usd": cost(model, s) if kind == "briefing" else None})
        print(f"{kind:8} {model:48} route {route or '-'}: TTFT {s['ttft'] or 0:6.2f}s total {s['total']:6.2f}s "
              f"out {s['tokens_out']} tok" + ("" if ok is None else f" complete={ok}"), flush=True)

    for m in a.models:  # first contact: may include a Modal cold start
        record("first", m, None, stream(m, PING, max_tokens=8))
    for _ in range(a.repeat):
        for _ in range(a.pings):
            for m in a.models:
                record("ping", m, None, stream(m, PING, max_tokens=8))
        for route, msgs, fmt, ids in reqs:
            for m in a.models:
                s = stream(m, msgs, fmt)
                record("briefing", m, route, s, complete(s["text"], ids))

    out = config.EVAL / "results"
    with open(out / "latency.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    fmt_s = lambda v: f"{v:.2f} s" if v is not None else "-"
    lines = ["# Latency: Nebius Token Factory vs our Modal deployment", "",
             f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC, from a laptop in Amsterdam. Streaming, sequential "
             f"requests interleaved across models, {a.repeat} rounds x 5 briefing requests + {a.pings} pings per "
             f"round. Briefing requests are the real model-stage calls for the labelled routes (json_schema output, "
             f"reasoning `{config.REASONING_EFFORT}`). Modal: vLLM 0.21 on one H100, cost counted as GPU-seconds at "
             f"${MODAL_GPU_USD_PER_S}/s while the request runs (idle GPU time is extra).", "",
             "| Model | Where | First call | Ping TTFT (median) | Briefing TTFT (median) | Briefing total (median) | "
             "Briefing total (p95) | Output tok/s | Complete JSON | Cost / briefing |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for m in a.models:
        first = next(r for r in rows if r["kind"] == "first" and r["model"] == m)
        pings = [r for r in rows if r["kind"] == "ping" and r["model"] == m]
        bs = [r for r in rows if r["kind"] == "briefing" and r["model"] == m]
        costs = [r["cost_usd"] for r in bs if r["cost_usd"] is not None]
        provider, name = config.split_model(m)
        lines.append(
            f"| {name.split('/')[-1]} | {'Modal (own H100)' if provider == 'modal' else 'Token Factory'} | "
            f"{fmt_s(first['total'])} | {fmt_s(med(r['ttft'] for r in pings))} | {fmt_s(med(r['ttft'] for r in bs))} | "
            f"{fmt_s(med(r['total'] for r in bs))} | {fmt_s(p95([r['total'] for r in bs]))} | "
            f"{med(r['decode_tps'] for r in bs) or 0:.0f} | {sum(bool(r['complete']) for r in bs)}/{len(bs)} | "
            f"{'$%.5f' % (sum(costs) / len(costs)) if costs else '-'} |")
    text = "\n".join(lines) + "\n"
    (out / "latency.md").write_text(text, encoding="utf-8")
    print("\n" + text)


if __name__ == "__main__":
    main()
