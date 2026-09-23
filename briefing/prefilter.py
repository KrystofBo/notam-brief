"""Deterministic pre-filter: keep NOTAMs whose circle, altitude band and validity overlap the flight.

Margins are generous on purpose. Recall matters more than precision at this stage; the model
stage removes what does not apply.
"""
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple

FIRS = {"NL": {"EHAA"}, "DE": {"EDWW", "EDGG", "EDMM", "EDXX"}}
WIDE_AREA_NM = 25  # Q-line circles this big bound a region; their centre says little about where the NOTAM applies


def country_of(code):
    return {"EH": "NL", "ED": "DE", "ET": "DE", "EB": "BE", "EL": "LU"}.get((code or "")[:2])


@dataclass
class Flight:
    dep: str
    dest: str
    path: List[Tuple[str, float, float]]  # (label, lat, lon), departure first and destination last
    start: datetime                       # window the NOTAMs are checked against (UTC)
    end: datetime
    alt_ft: int = 3000                    # planned maximum altitude, ft AMSL
    alternate: Optional[str] = None
    dep_time: Optional[datetime] = None   # planned off-block time when known, else only the window is known
    arr_time: Optional[datetime] = None
    corridor_nm: float = 10
    band_fl: Optional[Tuple[int, int]] = None
    aircraft: str = "single-engine piston (e.g. PA-28 / C172), MTOW under 5700 kg"
    countries: set = field(init=False)

    def __post_init__(self):
        if self.band_fl is None:
            self.band_fl = (0, max(65, math.ceil((self.alt_ft + 1500) / 100)))
        codes = [self.dep, self.dest, self.alternate] + [p[0] for p in self.path]
        self.countries = {c for c in map(country_of, codes) if c}

    @property
    def aerodromes(self):
        return {c for c in (self.dep, self.dest, self.alternate) if c}

    @property
    def points(self):
        return [(lat, lon) for _, lat, lon in self.path]

    @property
    def firs(self):
        return set().union(*(FIRS.get(c, set()) for c in self.countries))

    @property
    def distance_nm(self):
        p = self.points
        return sum(nm_between(a, b) for a, b in zip(p, p[1:]))


def nm_between(a, b):
    """Great-circle distance in nm."""
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * math.asin(math.sqrt(h)) * 3440.065


def _xy(lat, lon, lat0):
    return lon * 60 * math.cos(math.radians(lat0)), lat * 60  # nm, flat-earth local projection


def route_position(lat, lon, pts):
    """Where a point lies relative to the route polyline.

    Returns (cross-track nm, along-track nm from departure, side, where): side is 'left' or 'right' of
    the direction of flight; where is 'start' or 'end' if the nearest route point is the departure or
    the destination itself, else 'abeam'."""
    lat0 = pts[0][0]
    px, py = _xy(lat, lon, lat0)
    best, done, last = None, 0.0, len(pts) - 2
    for i, (a, b) in enumerate(zip(pts, pts[1:])):
        (ax, ay), (bx, by) = _xy(*a, lat0), _xy(*b, lat0)
        dx, dy = bx - ax, by - ay
        t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / ((dx * dx + dy * dy) or 1)))
        d = math.hypot(px - ax - t * dx, py - ay - t * dy)
        if best is None or d < best[0]:
            where = "start" if (i == 0 and t == 0) else "end" if (i == last and t == 1) else "abeam"
            cross = dx * (py - ay) - dy * (px - ax)  # > 0: left of the direction of flight
            best = (d, done + t * math.hypot(dx, dy), "left" if cross > 0 else "right", where)
        done += math.hypot(dx, dy)
    return best


def dist_to_path_nm(lat, lon, pts):
    return route_position(lat, lon, pts)[0]


def geometry(n, f):
    """Where a NOTAM sits relative to the flight, in words, for the model and the pilot."""
    a = set(n.get("a") or [])
    for code, role in ((f.dep, "departure"), (f.dest, "destination"), (f.alternate, "alternate")):
        if code and code in a:
            return f"at the {role} aerodrome {code}"
    if n.get("lat") is None:
        return None
    r = n["radius_nm"]
    if r >= 999:
        return "covers the whole FIR"
    if r >= WIDE_AREA_NM:
        return (f"wide-area NOTAM: its Q-line circle (radius {r} nm) only bounds a large region, "
                f"so judge from the E) text whether it applies to this route")
    d, along, side, where = route_position(n["lat"], n["lon"], f.points)
    if where == "start":
        pos = f"circle centre {d:.1f} nm from the departure aerodrome {f.dep}"
    elif where == "end":
        pos = f"circle centre {d:.1f} nm from the destination aerodrome {f.dest}"
    elif d < 0.5:
        pos = f"circle centre on the track, {along:.0f} nm after departure"
    else:
        pos = f"circle centre {d:.1f} nm {side} of the track, abeam a point {along:.0f} nm after departure"
    return pos + f"; radius {r} nm" + ("; the route passes through the circle" if d <= r else "")


def schedule_note(sched, f):
    """Flag a simple daily schedule that falls outside the flight window. The NOTAM is kept anyway."""
    m = re.fullmatch(r"DAILY (\d{4})-(\d{4})", (sched or "").strip())
    if not m or (f.end - f.start).days >= 1:
        return None
    s, e = int(m[1]), int(m[2])
    lo, hi = f.start.hour * 100 + f.start.minute, f.end.hour * 100 + f.end.minute
    active = (s <= e and s < hi and e > lo) or (s > e and (s < hi or e > lo))
    return None if active else f"schedule {sched} is outside {lo:04d}-{hi:04d}Z"


def _valid_in_window(n, f):
    vf, vt = n.get("valid_from"), n.get("valid_to")
    return not ((vf and vf > f.end) or (vt and vt < f.start))


def candidates(notams, f):
    """NOTAMs near the route, in bulletin order, each with the reason it was kept."""
    keep = []
    for n in notams:
        if not _valid_in_window(n, f):
            continue
        why = None
        if f.aerodromes & set(n.get("a", [])):
            why = "departure/destination aerodrome"
        elif n.get("lat") is not None:
            if n["lower_fl"] > f.band_fl[1] or n["upper_fl"] < f.band_fl[0]:
                continue
            if n["radius_nm"] >= 999:
                if n["q_fir"] in f.firs:
                    why = "FIR-wide"
            else:
                d = dist_to_path_nm(n["lat"], n["lon"], f.points)
                if d <= n["radius_nm"] + f.corridor_nm:
                    why = f"{d:.1f} nm from route (radius {n['radius_nm']} nm)"
        if why:
            keep.append(dict(n, keep_reason=why, schedule_note=schedule_note(n.get("schedule"), f)))
    return keep


def national_set(notams, f):
    """Baseline without the pre-filter: every NOTAM in the bulletins of the countries the flight touches."""
    return [dict(n, keep_reason="national bulletin", schedule_note=None)
            for n in notams if n["country"] in f.countries]
