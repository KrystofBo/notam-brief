"""Benchmark models x {pre-filter on, off} on the five labelled routes (frozen snapshot).

    python -m eval.bench                                          # default model, pre-filter on
    python -m eval.bench --models deepseek-ai/DeepSeek-V4-Flash-0731 other/model --modes prefilter full
    python -m eval.bench --reasoning none default                # reasoning off vs the model's default
    python -m eval.bench --hints on off                           # with and without the computed route geometry
    python -m eval.bench --combine eval/results/A eval/results/B   # one summary for several runs

Writes eval/results/<utc-stamp>/: one JSON per run, summary.csv and summary.md.
Recall is the metric that matters: a missed relevant NOTAM is the real failure.
"""
import argparse
import csv
import hashlib
import json
import re
import traceback
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from briefing import config, llm, pipeline

RESULTS = config.EVAL / "results"
KEYS = ("model", "mode", "hints", "reasoning", "prompt")


def load_labels():
    lab = defaultdict(dict)
    with open(config.EVAL / "labels_flat.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            lab[int(r["route"])][r["notam_id"]] = {"relevant": r["relevant"] == "1", "priority": r["priority"] or None}
    return lab


def score(out, labels):
    truth = {i for i, l in labels.items() if l["relevant"]}
    pred = {x["id"] for x in out["relevant"]}
    tp = pred & truth
    high = {i for i in truth if labels[i]["priority"] == "HIGH"}
    same_pri = sum(1 for x in out["relevant"] if x["id"] in truth and labels[x["id"]]["priority"] == x["priority"])
    return {
        "labelled": len(truth), "flagged": len(pred), "tp": len(tp),
        "recall": len(tp) / len(truth) if truth else 1.0,
        "precision": len(tp) / len(pred) if pred else float(not truth),
        "high_recall": len(high & pred) / len(high) if high else 1.0,
        "priority_match": same_pri / len(tp) if tp else None,
        "unassessed": len(out["unassessed"]),
        "missed": sorted(truth - pred),
        "false_pos": sorted(pred - truth),
        "unlabelled_flagged": sorted(i for i in pred - truth if i not in labels),
    }


def slug(model):
    return re.sub(r"[^A-Za-z0-9.-]+", "_", model.split("/")[-1])


def fmt(v, pct=False):
    if v is None:
        return "-"
    return f"{v:.0%}" if pct else (f"{v:.5f}" if isinstance(v, float) and v < 0.01 else f"{v:.3g}" if isinstance(v, float) else str(v))


def _ms(v):
    return f"{v:.1f} ms" if v is not None else "-"


def summarise(rows):
    groups = defaultdict(list)
    for r in rows:
        if "error" not in r:
            groups[tuple(r[k] for k in KEYS)].append(r)
    agg = []
    for key, rs in groups.items():
        labelled, flagged, tp = (sum(r[k] for r in rs) for k in ("labelled", "flagged", "tp"))
        costs = [r["cost_usd"] for r in rs if r["cost_usd"] is not None]
        pf = [r["prefilter_ms"] for r in rs if r.get("prefilter_ms") is not None]
        agg.append(dict(zip(KEYS, key), routes=len(rs),
                        recall=tp / labelled if labelled else None, precision=tp / flagged if flagged else None,
                        items_to_read=flagged / len(rs), sent_to_model=sum(r["sent"] for r in rs) / len(rs),
                        tokens_in=sum(r["tokens_in"] for r in rs) / len(rs),
                        tokens_out=sum(r["tokens_out"] for r in rs) / len(rs),
                        cost_usd=sum(costs) / len(costs) if costs else None,
                        prefilter_ms=sum(pf) / len(pf) if pf else None,
                        latency_s=sum(r["latency_s"] for r in rs) / len(rs)))
    return agg


def write(outdir, rows):
    cols = ["model", "mode", "hints", "reasoning", "prompt", "route", "run", "labelled", "flagged", "tp", "recall", "precision",
            "high_recall", "priority_match", "sent", "tokens_in", "tokens_out", "cost_usd", "prefilter_ms", "latency_s",
            "calls", "unassessed", "missed", "false_pos", "unlabelled_flagged", "error"]
    with open(outdir / "summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    on_off = lambda mode: "on" if mode == "prefilter" else "off"
    short = lambda m: m.split("/")[-1]
    md = ["# Benchmark results", "", f"Snapshot `{pipeline.eval_routes()['snapshot']}`, labels `eval/labels_flat.csv`. "
          "Recall and precision are pooled over routes; the other columns are means per briefing. *Hints* is the "
          "computed route geometry given to the model; *Prompt* is the first 7 hex digits of the system prompt's SHA-1.",
          "",
          "| Model | Pre-filter | Hints | Reasoning | Prompt | Recall | Precision | Items to read | NOTAMs sent | "
          "Tokens in | Tokens out | Cost / briefing | Pre-filter time | Model latency |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for a in summarise(rows):
        md.append(f"| {short(a['model'])} | {on_off(a['mode'])} | {a['hints']} | {a['reasoning']} | {a['prompt']} | "
                  f"{fmt(a['recall'], 1)} | {fmt(a['precision'], 1)} | {a['items_to_read']:.1f} | "
                  f"{a['sent_to_model']:.0f} | {a['tokens_in']:,.0f} | {a['tokens_out']:,.0f} | "
                  f"{'$' + fmt(a['cost_usd']) if a['cost_usd'] is not None else '-'} | {_ms(a['prefilter_ms'])} | "
                  f"{a['latency_s']:.1f} s |")
    md += ["", "## Per route", "",
           "| Model | Pre-filter | Hints | Reasoning | Prompt | Route (run) | Recall | Precision | Flagged / labelled | "
           "Missed | False positives | Tokens in/out | Cost | Pre-filter time | Model latency |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        head = (f"| {short(r['model'])} | {on_off(r['mode'])} | {r['hints']} | {r['reasoning']} | {r['prompt']} | "
                f"{r['route']}{' (' + str(r['run']) + ')' if r.get('run') else ''} |")
        if "error" in r:
            md.append(f"{head} error: {r['error'][:80]} |||||||||")
            continue
        md.append(f"{head} {fmt(r['recall'], 1)} | {fmt(r['precision'], 1)} | {r['flagged']} / {r['labelled']} | "
                  f"{r['missed'] or '-'} | {r['false_pos'] or '-'} | {r['tokens_in']:,} / {r['tokens_out']:,} | "
                  f"{'$' + fmt(r['cost_usd']) if r['cost_usd'] is not None else '-'} | {_ms(r.get('prefilter_ms'))} | "
                  f"{r['latency_s']:.1f} s |")
    text = "\n".join(md) + "\n"
    (outdir / "summary.md").write_text(text, encoding="utf-8")
    (RESULTS / "latest.md").write_text(text.replace("# Benchmark results", f"# Benchmark results ({outdir.name})", 1),
                                       encoding="utf-8")
    return text


NUMERIC = {"route": int, "run": int, "labelled": int, "flagged": int, "tp": int, "recall": float, "precision": float,
           "high_recall": float, "priority_match": float, "sent": int, "tokens_in": int, "tokens_out": int,
           "cost_usd": float, "prefilter_ms": float, "latency_s": float, "calls": int, "unassessed": int}


def load_rows(d):
    rows = []
    with open(Path(d) / "summary.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            for k, cast in NUMERIC.items():
                if k in r:
                    r[k] = cast(r[k]) if r[k] != "" else None
            if not r.get("error"):
                r.pop("error", None)
            r.setdefault("hints", "off")  # runs from before the geometry hints existed
            r.setdefault("prompt", "earlier")
            rows.append(r)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--combine", nargs="+", metavar="DIR", help="merge earlier result folders into one summary")
    ap.add_argument("--models", nargs="+", default=[config.DEFAULT_MODEL])
    ap.add_argument("--modes", nargs="+", default=["prefilter"], choices=["prefilter", "full"])
    ap.add_argument("--hints", nargs="+", default=["off"], choices=["on", "off"],
                    help="give the model each NOTAM's computed position relative to the route (pre-filter mode)")
    ap.add_argument("--routes", nargs="+", type=int, default=[1, 2, 3, 4, 5])
    ap.add_argument("--weather", action="store_true", help="include live METAR/TAF (off by default: not reproducible)")
    ap.add_argument("--chunk", type=int, default=80, help="NOTAMs per model request")
    ap.add_argument("--reasoning", nargs="+", default=[config.REASONING_EFFORT],
                    help="reasoning_effort values to compare, e.g. none default")
    ap.add_argument("--parallel", type=int, default=5, help="briefings run at once (use 1 for --modes full)")
    ap.add_argument("--repeat", type=int, default=1, help="run every briefing this many times (outputs vary a little)")
    a = ap.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    if a.combine:
        outdir = RESULTS / f"{stamp}-combined"
        outdir.mkdir(parents=True)
        print(write(outdir, [r for d in a.combine for r in load_rows(d)]))
        return
    cfg, labels = pipeline.eval_routes(), load_labels()
    prompt = hashlib.sha1(llm.SYSTEM_PROMPT.encode("utf-8")).hexdigest()[:7]
    outdir = RESULTS / stamp
    outdir.mkdir(parents=True)
    jobs = [(model, mode, hints, reasoning, r, i) for i in range(1, a.repeat + 1) for model in a.models
            for mode in a.modes for hints in (a.hints if mode == "prefilter" else ["off"]) for reasoning in a.reasoning
            for r in cfg["routes"] if r["id"] in a.routes]

    def run(job):
        model, mode, hints, reasoning, r, i = job
        base = {"model": model, "mode": mode, "hints": hints, "reasoning": reasoning, "prompt": prompt, "route": r["id"],
                "run": i}
        try:
            out = pipeline.brief(r["dep"], r["dest"], path=r["path"], route_note=r.get("note"),
                                 window=cfg["window"], band_fl=tuple(cfg["band_fl"]), corridor_nm=cfg["corridor_nm"],
                                 alt_ft=cfg["alt_ft"], model=model, source=cfg["snapshot"],
                                 use_prefilter=mode == "prefilter", with_weather=a.weather, chunk_size=a.chunk,
                                 reasoning=reasoning, hints=hints == "on")
        except Exception as e:
            traceback.print_exc()
            return dict(base, error=str(e))
        s = score(out, labels[r["id"]])
        m = out["model"]
        row = dict(base, **{k: (" ".join(v) if isinstance(v, list) else v) for k, v in s.items()},
                   sent=out["counts"]["candidates"], tokens_in=m["usage"]["prompt_tokens"],
                   tokens_out=m["usage"]["completion_tokens"], cost_usd=m["cost_usd"],
                   prefilter_ms=out["timing"]["prefilter_ms"], latency_s=m["latency_s"], calls=m["calls"])
        (outdir / f"{slug(model)}_{mode}_hints-{hints}_{reasoning}_route{r['id']}_run{i}.json").write_text(
            json.dumps(dict(out, score=s), indent=1, default=str), encoding="utf-8")
        print(f"{slug(model):24} {mode:9} hints {hints:3} {reasoning:7} route {r['id']} run {i}: "
              f"recall {fmt(row['recall'], 1):>4} precision {fmt(row['precision'], 1):>4} "
              f"flagged {row['flagged']:>2}/{row['labelled']} missed [{row['missed']}] "
              f"prefilter {row['prefilter_ms']:.1f} ms, model {m['latency_s']:.1f} s", flush=True)
        return row

    with ThreadPoolExecutor(max_workers=max(1, a.parallel)) as pool:
        rows = list(pool.map(run, jobs))
    print()
    print(write(outdir, rows))
    print(f"results in {outdir}")


if __name__ == "__main__":
    main()
