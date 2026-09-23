"""Write eval/routes/routeN_notams.txt: each test route's pre-filtered NOTAMs, verbatim and in bulletin
order, under the bulletin's own FIR / section / aerodrome headings.

    python -m eval.export_routes
"""
from briefing import config, ingest, prefilter
from briefing.pipeline import eval_routes, make_flight


def main():
    cfg = eval_routes()
    notams, bulletins = ingest.load(cfg["snapshot"])
    titles = {b["country"]: b["title"] for b in bulletins}
    for r in cfg["routes"]:
        f = make_flight(r["dep"], r["dest"], path=r["path"], window=cfg["window"], alt_ft=cfg["alt_ft"],
                        band_fl=tuple(cfg["band_fl"]), corridor_nm=cfg["corridor_nm"])
        keep = prefilter.candidates(notams, f)
        out = [f"ROUTE {r['id']}: {r['name']}",
               f"Flight window {cfg['window'][0]} to {cfg['window'][1]}, GND-FL{cfg['band_fl'][1]:03d}, "
               f"corridor {cfg['corridor_nm']} nm + NOTAM radius",
               f"{len(keep)} NOTAMs, in bulletin order and verbatim.", ""]
        country, last = None, (None, None, None)
        for n in keep:
            if n["country"] != country:
                country, last = n["country"], (None, None, None)
                out += ["=" * 72, titles[country], "=" * 72, ""]
            heads = (n["fir"], n["section"], n["aerodrome"])
            changed = False
            for i, h in enumerate(heads):
                changed = changed or h != last[i]
                if h and changed:
                    out += [["#", "##", "###"][i] + " " + h, ""]
            last = heads
            out += [n["raw"], ""]
        path = config.EVAL / "routes" / f"route{r['id']}_notams.txt"
        path.write_text("\n".join(out), encoding="utf-8")
        print(f"route {r['id']}: {len(keep)} NOTAMs -> {path.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()
