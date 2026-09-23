"""End to end: bulletins -> pre-filter -> weather -> model -> ranked briefing.

    python -m briefing.pipeline EHLE EHHV --time 2026-09-23T09:00
"""
import argparse
import json
import time
from datetime import datetime, timedelta, timezone

from . import aerodromes, config, ingest, llm, prefilter, sun, weather

UTC = timezone.utc
PRI = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def eval_routes():
    return json.loads((config.EVAL / "routes.json").read_text(encoding="utf-8"))


def _utc(t):
    if t is None or isinstance(t, datetime):
        return t.astimezone(UTC) if t and t.tzinfo else (t.replace(tzinfo=UTC) if t else None)
    return _utc(datetime.fromisoformat(str(t).replace("Z", "+00:00")))


def make_flight(dep, dest, via=(), alternate=None, dep_time=None, window=None, alt_ft=3000, tas_kt=95,
                path=None, **kw):
    dep, dest = dep.strip().upper(), dest.strip().upper()
    alternate = (alternate or "").strip().upper() or None
    for code in filter(None, (dep, dest, alternate)):
        if not aerodromes.get(code):
            raise ValueError(f"Unknown aerodrome {code}")
    pts = [(p[0], float(p[1]), float(p[2])) for p in path] if path else \
        [aerodromes.parse_point(p) for p in (dep, *via, dest)]
    dist = sum(prefilter.nm_between(a[1:], b[1:]) for a, b in zip(pts, pts[1:]))
    arr = None
    if window:
        start, end = map(_utc, window)
        dep_time = None
    else:
        dep_time = _utc(dep_time) or (datetime.now(UTC) + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        arr = dep_time + timedelta(hours=dist / tas_kt)
        start, end = dep_time - timedelta(hours=1), arr + timedelta(hours=1)
    return prefilter.Flight(dep=dep, dest=dest, path=pts, start=start, end=end, alt_ft=alt_ft,
                            alternate=alternate, dep_time=dep_time, arr_time=arr, **kw)


def flight_block(f, route_note=None):
    mid = f.points[len(f.points) // 2]
    rise, sset = sun.sunrise_sunset(mid[0], mid[1], f.start)
    route = " - ".join(label for label, _, _ in f.path) + f", {f.distance_nm:.0f} nm"
    if route_note:
        route += f" ({route_note})"
    if f.dep_time:
        when = (f"planned departure {f.dep_time:%Y-%m-%d %H%M}Z, estimated arrival {f.arr_time:%H%M}Z "
                f"(NOTAMs checked for {f.start:%H%M}Z-{f.end:%H%M}Z)")
    else:
        when = (f"flight window {f.start:%Y-%m-%d %H%M}Z to {f.end:%H%M}Z; the departure time is not fixed, "
                f"so judge each NOTAM for any time in this window")
    alt = f"{f.alternate} ({aerodromes.name(f.alternate)})" if f.alternate else "none"
    return "\n".join([
        f"Departure: {f.dep} ({aerodromes.name(f.dep)})",
        f"Destination: {f.dest} ({aerodromes.name(f.dest)})",
        f"Alternate: {alt}",
        f"Route: {route}",
        f"Time: {when}",
        f"Daylight: sunrise {rise:%H%M}Z, sunset {sset:%H%M}Z",
        f"Altitude: GND to {f.alt_ft} ft AMSL",
        f"Aircraft: {f.aircraft}",
        "Flight rules: VFR",
    ])


def _iso(t):
    return t.isoformat().replace("+00:00", "Z") if t else None


def _location(n):
    if n.get("aerodrome"):
        return n["aerodrome"]
    where = " ".join(n.get("a") or []) or n.get("q_fir") or ""
    return f"{where} {n.get('section') or ''}".strip()


def brief(dep, dest, *, via=(), alternate=None, dep_time=None, window=None, alt_ft=3000, path=None,
          route_note=None, model=None, source="live", use_prefilter=True, with_weather=True, chunk_size=80,
          band_fl=None, corridor_nm=10, reasoning=None, hints=False):
    """hints: also give the model each NOTAM's computed position relative to the route. Off by default: on the
    labelled routes it made DeepSeek-V4-Flash flag more distant items (precision 56% vs 64%, recall 100% either
    way). The position is always returned for the pilot."""
    model = model or config.DEFAULT_MODEL
    reasoning = reasoning or config.REASONING_EFFORT  # "none", "default", "low", "medium" or "high"
    clock = time.perf_counter
    t0 = clock()
    notams, bulletins = ingest.load(source)
    t_ingest = clock() - t0
    f = make_flight(dep, dest, via=via, alternate=alternate, dep_time=dep_time, window=window, alt_ft=alt_ft,
                    path=path, band_fl=band_fl, corridor_nm=corridor_nm)
    t1 = clock()
    national = prefilter.national_set(notams, f)
    cands = prefilter.candidates(notams, f) if use_prefilter else national
    for n in cands:
        n["geometry"] = prefilter.geometry(n, f) if use_prefilter else None
    t_filter = clock() - t1
    t2 = clock()
    wx = weather.for_flight(f) if with_weather else {"stations": [], "text": ""}
    t_weather = clock() - t2
    model_input = cands if hints else [dict(n, geometry=None) for n in cands]
    res = llm.assess(model, flight_block(f, route_note), wx["text"], model_input, chunk_size=chunk_size,
                     reasoning_effort=None if reasoning == "default" else reasoning)

    items = []
    for i, (n, r) in enumerate(zip(cands, res["items"])):
        items.append(dict(r, order=i, raw=n["raw"], location=_location(n), keep_reason=n["keep_reason"],
                          geometry=n.get("geometry"), schedule=n.get("schedule"), schedule_note=n.get("schedule_note"),
                          valid_from=_iso(n.get("valid_from")), valid_to=_iso(n.get("valid_to")),
                          valid_to_raw=n.get("c")))
    relevant = sorted((x for x in items if x["relevant"]), key=lambda x: (PRI[x["priority"]], x["order"]))
    return {
        "flight": {"dep": f.dep, "dest": f.dest, "alternate": f.alternate, "dep_name": aerodromes.name(f.dep),
                   "dest_name": aerodromes.name(f.dest), "path": f.path, "distance_nm": round(f.distance_nm, 1),
                   "dep_time": _iso(f.dep_time), "arr_time": _iso(f.arr_time), "window": [_iso(f.start), _iso(f.end)],
                   "alt_ft": f.alt_ft, "band_fl": f.band_fl, "corridor_nm": f.corridor_nm},
        "bulletins": [dict(b, generated=_iso(b["generated"])) for b in bulletins if b["country"] in f.countries],
        "source": source,
        "prefilter": use_prefilter,
        "hints": bool(hints and use_prefilter),
        "counts": {"national": len(national), "candidates": len(cands), "relevant": len(relevant),
                   "unassessed": sum(not x["assessed"] for x in items)},
        "weather": {"summary": res["weather_summary"], "stations": wx["stations"], "error": wx.get("error")},
        "relevant": relevant,
        "unassessed": [x for x in items if not x["assessed"]],
        "not_relevant": [x for x in items if x["assessed"] and not x["relevant"]],
        "model": {"id": model, "reasoning": reasoning, "usage": res["usage"], "cost_usd": res["cost_usd"],
                  "latency_s": round(res["latency_s"], 2), "calls": res["calls"], "errors": res["errors"]},
        "timing": {"ingest_ms": round(t_ingest * 1000, 1), "prefilter_ms": round(t_filter * 1000, 2),
                   "weather_ms": round(t_weather * 1000), "model_s": round(res["latency_s"], 2),
                   "total_s": round(clock() - t0, 2)},
    }


def main():
    ap = argparse.ArgumentParser(description="Print a route briefing as JSON.")
    ap.add_argument("dep")
    ap.add_argument("dest")
    ap.add_argument("--via", nargs="*", default=[])
    ap.add_argument("--alternate")
    ap.add_argument("--time", help="planned departure, UTC ISO (default: next full hour)")
    ap.add_argument("--alt", type=int, default=3000, help="planned max altitude, ft AMSL")
    ap.add_argument("--model")
    ap.add_argument("--source", default="live", help="'live' or a snapshot name such as 2026-09-22")
    ap.add_argument("--no-prefilter", action="store_true")
    ap.add_argument("--reasoning", help="none (default), default, low, medium or high")
    ap.add_argument("--hints", action="store_true", help="also give the model the computed route geometry")
    a = ap.parse_args()
    out = brief(a.dep, a.dest, via=a.via, alternate=a.alternate, dep_time=a.time, alt_ft=a.alt, model=a.model,
                source=a.source, use_prefilter=not a.no_prefilter, reasoning=a.reasoning, hints=a.hints)
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
