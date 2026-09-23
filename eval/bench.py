"""Benchmark models x {pre-filter on, off} on the five labelled routes (frozen snapshot).

    python -m eval.bench                                          # default model, pre-filter on
    python -m eval.bench --models deepseek-ai/DeepSeek-V4-Flash-0731 other/model --modes prefilter full

Writes eval/results/<utc-stamp>/: one JSON per run, summary.csv and summary.md.
Recall is the metric that matters: a missed relevant NOTAM is the real failure.
"""
import argparse
import csv
import json
import re
import traceback
from collections import defaultdict
from datetime import datetime, timezone

from briefing import config, pipeline

RESULTS = config.EVAL / "results"


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


def summarise(rows):
    groups = defaultdict(list)
    for r in rows:
        if "error" not in r:
            groups[(r["model"], r["mode"])].append(r)
    agg = []
    for (model, mode), rs in groups.items():
        labelled, flagged, tp = (sum(r[k] for r in rs) for k in ("labelled", "flagged", "tp"))
        costs = [r["cost_usd"] for r in rs if r["cost_usd"] is not None]
        agg.append({"model": model, "mode": mode, "routes": len(rs),
                    "recall": tp / labelled if labelled else None, "precision": tp / flagged if flagged else None,
                    "items_to_read": flagged / len(rs), "sent_to_model": sum(r["sent"] for r in rs) / len(rs),
                    "tokens_in": sum(r["tokens_in"] for r in rs) / len(rs),
                    "tokens_out": sum(r["tokens_out"] for r in rs) / len(rs),
                    "cost_usd": sum(costs) / len(costs) if costs else None,
                    "latency_s": sum(r["latency_s"] for r in rs) / len(rs)})
    return agg


def write(outdir, rows):
    cols = ["model", "mode", "route", "labelled", "flagged", "tp", "recall", "precision", "high_recall", "priority_match",
            "sent", "tokens_in", "tokens_out", "cost_usd", "latency_s", "calls", "unassessed", "missed", "false_pos",
            "unlabelled_flagged", "error"]
    with open(outdir / "summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    agg = summarise(rows)
    md = ["# Benchmark results", "", f"Snapshot `{pipeline.eval_routes()['snapshot']}`, labels `eval/labels_flat.csv`. "
          "Recall and precision are pooled over routes; the other columns are means per briefing.", "",
          "| Model | Pre-filter | Recall | Precision | Items to read | NOTAMs sent | Tokens in | Tokens out | Cost / briefing | Latency |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for a in agg:
        md.append(f"| {a['model']} | {'on' if a['mode'] == 'prefilter' else 'off'} | {fmt(a['recall'], 1)} | "
                  f"{fmt(a['precision'], 1)} | {a['items_to_read']:.1f} | {a['sent_to_model']:.0f} | {a['tokens_in']:,.0f} | "
                  f"{a['tokens_out']:,.0f} | {'$' + fmt(a['cost_usd']) if a['cost_usd'] is not None else '-'} | {a['latency_s']:.1f} s |")
    md += ["", "## Per route", "",
           "| Model | Pre-filter | Route | Recall | Precision | Flagged / labelled | Missed | False positives | Tokens in/out | Cost | Latency |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if "error" in r:
            md.append(f"| {r['model']} | {r['mode']} | {r['route']} | error: {r['error'][:80]} |||||||||")
            continue
        md.append(f"| {r['model'].split('/')[-1]} | {'on' if r['mode'] == 'prefilter' else 'off'} | {r['route']} | "
                  f"{fmt(r['recall'], 1)} | {fmt(r['precision'], 1)} | {r['flagged']} / {r['labelled']} | "
                  f"{r['missed'] or '-'} | {r['false_pos'] or '-'} | {r['tokens_in']:,} / {r['tokens_out']:,} | "
                  f"{'$' + fmt(r['cost_usd']) if r['cost_usd'] is not None else '-'} | {r['latency_s']:.1f} s |")
    text = "\n".join(md) + "\n"
    (outdir / "summary.md").write_text(text, encoding="utf-8")
    (RESULTS / "latest.md").write_text(text.replace("# Benchmark results", f"# Benchmark results ({outdir.name})", 1),
                                       encoding="utf-8")
    return text


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", nargs="+", default=[config.DEFAULT_MODEL])
    ap.add_argument("--modes", nargs="+", default=["prefilter"], choices=["prefilter", "full"])
    ap.add_argument("--routes", nargs="+", type=int, default=[1, 2, 3, 4, 5])
    ap.add_argument("--weather", action="store_true", help="include live METAR/TAF (off by default: not reproducible)")
    ap.add_argument("--chunk", type=int, default=80, help="NOTAMs per model request")
    a = ap.parse_args()

    cfg, labels = pipeline.eval_routes(), load_labels()
    outdir = RESULTS / datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    outdir.mkdir(parents=True)
    rows = []
    for model in a.models:
        for mode in a.modes:
            for r in (r for r in cfg["routes"] if r["id"] in a.routes):
                base = {"model": model, "mode": mode, "route": r["id"]}
                try:
                    out = pipeline.brief(r["dep"], r["dest"], path=r["path"], route_note=r.get("note"),
                                         window=cfg["window"], band_fl=tuple(cfg["band_fl"]),
                                         corridor_nm=cfg["corridor_nm"], alt_ft=cfg["alt_ft"], model=model,
                                         source=cfg["snapshot"], use_prefilter=mode == "prefilter",
                                         with_weather=a.weather, chunk_size=a.chunk)
                except Exception as e:
                    traceback.print_exc()
                    rows.append(dict(base, error=str(e)))
                    continue
                s = score(out, labels[r["id"]])
                m = out["model"]
                row = dict(base, **{k: (" ".join(v) if isinstance(v, list) else v) for k, v in s.items()},
                           sent=out["counts"]["candidates"], tokens_in=m["usage"]["prompt_tokens"],
                           tokens_out=m["usage"]["completion_tokens"], cost_usd=m["cost_usd"],
                           latency_s=m["latency_s"], calls=m["calls"])
                rows.append(row)
                (outdir / f"{slug(model)}_{mode}_route{r['id']}.json").write_text(
                    json.dumps(dict(out, score=s), indent=1, default=str), encoding="utf-8")
                print(f"{slug(model):28} {mode:9} route {r['id']}: recall {fmt(row['recall'], 1):>4} "
                      f"precision {fmt(row['precision'], 1):>4} flagged {row['flagged']:>2}/{row['labelled']} "
                      f"missed [{row['missed']}] tokens {row['tokens_in']}/{row['tokens_out']} "
                      f"{m['latency_s']:.1f}s")
    print()
    print(write(outdir, rows))
    print(f"results in {outdir}")


if __name__ == "__main__":
    main()
