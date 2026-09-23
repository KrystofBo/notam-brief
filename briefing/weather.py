"""METAR and TAF from the aviationweather.gov data API (free, no key).

Many small fields (EHHV, EHTE, EHHO, EHTX, EHTW) publish no METAR, so each aerodrome falls back
to the nearest reporting station, preferring stations that also issue a TAF.
"""
import requests

from . import aerodromes
from .prefilter import nm_between

API = "https://aviationweather.gov/api/data/{}"
MAX_FALLBACK_NM = 60


def _get(kind, bbox):
    r = requests.get(API.format(kind), params={"bbox": ",".join(f"{v:.2f}" for v in bbox), "format": "json"},
                     timeout=30)
    if r.status_code == 204 or not r.content.strip():
        return []
    r.raise_for_status()
    return r.json()


def _pick(code, lat, lon, metars, tafs):
    if code in metars:
        return code, 0.0
    ranked = sorted((nm_between((lat, lon), (m["lat"], m["lon"])), m["icaoId"]) for m in metars.values())
    ranked = [(d, s) for d, s in ranked if d <= MAX_FALLBACK_NM]
    with_taf = [(d, s) for d, s in ranked if s in tafs]
    best = (with_taf or ranked or [(None, None)])[0]
    return best[1], best[0]


def for_flight(f, margin_deg=0.8):
    lats = [p[0] for p in f.points]
    lons = [p[1] for p in f.points]
    bbox = (min(lats) - margin_deg, min(lons) - margin_deg, max(lats) + margin_deg, max(lons) + margin_deg)
    try:
        metars = {m["icaoId"]: m for m in _get("metar", bbox)}
        tafs = {t["icaoId"]: t for t in _get("taf", bbox)}
    except (requests.RequestException, ValueError) as e:
        return {"stations": [], "text": "", "error": f"weather unavailable: {e}"}
    stations, lines = [], []
    for role, code in (("departure", f.dep), ("destination", f.dest), ("alternate", f.alternate)):
        ad = aerodromes.get(code) if code else None
        if not ad:
            continue
        station, dist = _pick(code, ad["lat"], ad["lon"], metars, tafs)
        if not station:
            lines.append(f"{code} ({role}): no weather report within {MAX_FALLBACK_NM} nm")
            continue
        m, t = metars[station], tafs.get(station)
        st = {"for": code, "role": role, "station": station, "distance_nm": round(dist, 1),
              "metar": m.get("rawOb", ""), "taf": (t or {}).get("rawTAF", ""), "name": m.get("name", "")}
        stations.append(st)
        head = (f"{code} ({role}), own report:" if station == code else
                f"{code} ({role}) has no METAR; nearest report {station}, {dist:.0f} nm away:")
        lines += [head, st["metar"]] + ([st["taf"]] if st["taf"] else []) + [""]
    return {"stations": stations, "text": "\n".join(lines).strip()}
