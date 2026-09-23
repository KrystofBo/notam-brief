"""Turn eval/labels.json into the scoring key (eval/labels_flat.csv) and a review page
(eval/labels_review.html). Edit labels.json, then re-run:

    python -m eval.build_labels
"""
import csv
import html
import json

from briefing import config, ingest, prefilter
from briefing.pipeline import eval_routes, make_flight

PRI = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
esc = html.escape


def default_reason(n, defaults):
    if n.get("q_fir") == "EDXX":
        return defaults["EDXX"]
    if "EHAM" in n.get("a", []):
        return defaults["EHAM"]
    if n.get("traffic") == "I" or n.get("q_code", "").startswith(("QPO", "QPI", "QPD", "QIC", "QIU")):
        return defaults["IFR"]
    if n.get("q_code", "").startswith("QOL"):
        return defaults["LIGHTS"]
    return defaults["FAR"]


CSS = """:root{--bg:#f7f7f5;--card:#fff;--fg:#1d1f22;--mut:#63676d;--line:#e2e2de;--code:#f0f0ec;
--hi:#c0392b;--hi-bg:#fbeceb;--me:#b7791f;--me-bg:#fdf5e6;--lo:#4a6fa5;--lo-bg:#edf2f9}
@media (prefers-color-scheme:dark){:root{--bg:#16181b;--card:#1f2226;--fg:#e7e7e4;--mut:#9a9ea4;--line:#33373c;--code:#181a1d;
--hi:#f0786b;--hi-bg:#3a2220;--me:#e6b35a;--me-bg:#352c1c;--lo:#8fb0de;--lo-bg:#1f2a38}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:24px;margin:0 0 4px}.sub{color:var(--mut);margin:0 0 16px}
nav{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 24px}nav a{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:6px 10px;color:inherit;text-decoration:none;font-size:14px}
.pill{color:var(--mut);font-variant-numeric:tabular-nums}
section{margin-top:36px}h2{font-size:19px;display:flex;align-items:center;gap:10px;margin:0 0 2px}
.num{display:inline-grid;place-items:center;width:26px;height:26px;border-radius:50%;background:var(--fg);color:var(--bg);font-size:14px}
.meta{color:var(--mut);margin:0 0 12px}
.item{display:grid;grid-template-columns:1fr 1fr;background:var(--card);border:1px solid var(--line);border-left:4px solid var(--c);border-radius:8px;margin:10px 0;overflow:hidden}
.high{--c:var(--hi);--cb:var(--hi-bg)}.medium{--c:var(--me);--cb:var(--me-bg)}.low{--c:var(--lo);--cb:var(--lo-bg)}
.plain{padding:12px 14px}.plain p{margin:6px 0 0}.why{color:var(--mut);font-size:13px}
.hdr{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.pri{background:var(--cb);color:var(--c);font-weight:600;font-size:12px;padding:2px 7px;border-radius:4px;letter-spacing:.03em}
.loc{color:var(--mut);font-size:13px}code{font-family:ui-monospace,Consolas,monospace;font-size:13px}
.icao{margin:0;padding:12px 14px;background:var(--code);border-left:1px solid var(--line);font:12px/1.45 ui-monospace,Consolas,monospace;white-space:pre-wrap;word-break:break-word;color:var(--mut)}
details{margin-top:10px}summary{cursor:pointer;color:var(--mut)}.drop{padding-left:18px;color:var(--mut);font-size:13px}.drop li{margin:3px 0}
.empty{color:var(--mut)}.note{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 14px;font-size:13px;color:var(--mut)}
@media (max-width:720px){.item{grid-template-columns:1fr}.icao{border-left:0;border-top:1px solid var(--line)}}"""


def main():
    cfg = eval_routes()
    labels = json.loads((config.EVAL / "labels.json").read_text(encoding="utf-8"))
    defaults = labels["_default_reasons"]
    notams, bulletins = ingest.load(cfg["snapshot"])
    rows, sections, toc = [], [], []
    for r in cfg["routes"]:
        rid = str(r["id"])
        f = make_flight(r["dep"], r["dest"], path=r["path"], window=cfg["window"], alt_ft=cfg["alt_ft"],
                        band_fl=tuple(cfg["band_fl"]), corridor_nm=cfg["corridor_nm"])
        cands = prefilter.candidates(notams, f)
        lab = labels["routes"][rid]
        notlab = lab.get("_not", {})
        rel = sorted(((n, lab[n["id"]]) for n in cands if n["id"] in lab), key=lambda x: PRI[x[1]["p"]])
        irr = [(n, notlab.get(n["id"], default_reason(n, defaults))) for n in cands if n["id"] not in lab]
        stale = set(lab) - {"_not"} - {n["id"] for n in cands}
        if stale:
            print(f"route {rid}: labelled but not a candidate any more: {sorted(stale)}")
        rows += [[rid, n["id"], 1, l["p"], l["r"]] for n, l in rel] + [[rid, n["id"], 0, "", why] for n, why in irr]

        toc.append(f'<a href="#r{rid}"><b>{rid}</b> {esc(r["name"])} <span class="pill">{len(rel)} / {len(cands)}</span></a>')
        cards = [f'''<article class="item {l['p'].lower()}">
  <div class="plain"><div class="hdr"><span class="pri">{l['p']}</span><code>{esc(n['id'])}</code><span class="loc">{esc(n.get('aerodrome') or ' '.join(n['a']))}</span></div>
  <p>{esc(l['s'])}</p><p class="why">Why it matters: {esc(l['r'])}</p></div>
  <pre class="icao">{esc(n['raw'])}</pre></article>''' for n, l in rel] or ['<p class="empty">No relevant NOTAMs.</p>']
        drop = "".join(f'<li><code>{esc(n["id"])}</code> {esc(why)}</li>' for n, why in irr)
        sections.append(f'''<section id="r{rid}"><h2><span class="num">{rid}</span>{esc(r["name"])}</h2>
<p class="meta">{len(cands)} candidates after the geometric pre-filter, <b>{len(rel)}</b> labelled relevant.</p>
{''.join(cards)}
<details><summary>{len(irr)} labelled not relevant, with reasons</summary><ul class="drop">{drop}</ul></details></section>''')

    with open(config.EVAL / "labels_flat.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["route", "notam_id", "relevant", "priority", "reason"])
        w.writerows(rows)

    stamps = ", ".join(f"{b['country']} {b['generated']:%d %b %Y %H:%MZ}" for b in bulletins)
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>NOTAM Label Review</title><style>{CSS}</style></head><body><main>
<h1>Relevance labels for the five test routes</h1>
<p class="sub">Snapshot {esc(cfg['snapshot'])} ({esc(stamps)}). Assumed flight: {esc(cfg['window'][0])} to {esc(cfg['window'][1])},
VFR single-engine piston, GND&ndash;FL{cfg['band_fl'][1]:03d}. Draft labels: a pilot must verify them before they count as ground truth.</p>
<nav>{''.join(toc)}</nav>
<p class="note">Pre-filter: the NOTAM circle is within its radius + {cfg['corridor_nm']} nm of the route, the altitude band overlaps the flight,
and validity overlaps the window. Departure and destination aerodrome NOTAMs are always kept.
Edit <code>eval/labels.json</code> and run <code>python -m eval.build_labels</code> to update this page and the scoring key.</p>
{''.join(sections)}
</main></body></html>'''
    (config.EVAL / "labels_review.html").write_text(page, encoding="utf-8")
    print(f"{len(rows)} labels -> eval/labels_flat.csv, eval/labels_review.html")


if __name__ == "__main__":
    main()
