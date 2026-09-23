"""Time the deterministic stages on the frozen snapshot: parsing both bulletins, and pre-filtering
(candidates + route geometry) for each test route. No network, no model.

    python -m eval.time_prefilter [--repeat 300]

Writes eval/results/prefilter_timing.md.
"""
import argparse
import platform
import statistics
import time

from briefing import config, ingest, prefilter
from briefing.pipeline import eval_routes, make_flight


def bench(fn, repeat):
    times = []
    for _ in range(repeat):
        t = time.perf_counter()
        out = fn()
        times.append((time.perf_counter() - t) * 1000)
    times.sort()
    return out, statistics.median(times), times[int(0.95 * (len(times) - 1))]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repeat", type=int, default=300)
    a = ap.parse_args()
    cfg = eval_routes()

    (notams, bulletins), parse_med, parse_p95 = bench(lambda: ingest.load(cfg["snapshot"]), max(10, a.repeat // 20))
    rows = []
    for r in cfg["routes"]:
        f = make_flight(r["dep"], r["dest"], path=r["path"], window=cfg["window"], alt_ft=cfg["alt_ft"],
                        band_fl=tuple(cfg["band_fl"]), corridor_nm=cfg["corridor_nm"])

        def run():
            cands = prefilter.candidates(notams, f)
            for n in cands:
                n["geometry"] = prefilter.geometry(n, f)
            return cands

        cands, med, p95 = bench(run, a.repeat)
        rows.append((r, len(notams), len(cands), med, p95))

    lines = ["# Pre-filter timing", "",
             f"Snapshot `{cfg['snapshot']}`: {len(notams)} NOTAMs (NL + DE). {a.repeat} runs per route. "
             f"{platform.python_implementation()} {platform.python_version()} on {platform.system()} "
             f"{platform.machine()} ({platform.processor() or 'unknown CPU'}).", "",
             f"Parsing both bulletin HTML files (done once per bulletin refresh, then cached): "
             f"median {parse_med:.1f} ms, p95 {parse_p95:.1f} ms.", "",
             "| Route | NOTAMs scanned | Kept | Median | p95 | Per NOTAM |", "|---|---|---|---|---|---|"]
    for r, n_in, n_out, med, p95 in rows:
        lines.append(f"| {r['id']} {r['name']} | {n_in} | {n_out} | {med:.2f} ms | {p95:.2f} ms | "
                     f"{med * 1000 / n_in:.1f} µs |")
    text = "\n".join(lines) + "\n"
    (config.EVAL / "results").mkdir(exist_ok=True)
    (config.EVAL / "results" / "prefilter_timing.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
