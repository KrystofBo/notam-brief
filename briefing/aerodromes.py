"""Aerodrome coordinates (OurAirports, public domain; NL/DE/BE/LU) and route point parsing."""
import csv
import re
from functools import lru_cache

from .config import DATA


@lru_cache(maxsize=1)
def table():
    with open(DATA / "aerodromes.csv", encoding="utf-8") as f:
        return {r["icao"]: dict(r, lat=float(r["lat"]), lon=float(r["lon"])) for r in csv.DictReader(f)}


def get(icao):
    return table().get((icao or "").strip().upper())


def name(icao):
    ad = get(icao)
    return ad["name"] if ad else icao


DECIMAL = re.compile(r"^(-?\d+(?:\.\d+)?)\s*[,/]\s*(-?\d+(?:\.\d+)?)$")
ICAO_POS = re.compile(r"^(\d{2})(\d{2})(\d{2})?([NS])(\d{3})(\d{2})(\d{2})?([EW])$")


def parse_point(token):
    """An ICAO aerodrome code, 'lat,lon' in decimal degrees, or 5230N00430E. Returns (label, lat, lon)."""
    t = token.strip().upper()
    ad = get(t)
    if ad:
        return t, ad["lat"], ad["lon"]
    m = DECIMAL.match(t)
    if m:
        return t, float(m[1]), float(m[2])
    m = ICAO_POS.match(t.replace(" ", ""))
    if m:
        lat = int(m[1]) + int(m[2]) / 60 + int(m[3] or 0) / 3600
        lon = int(m[5]) + int(m[6]) / 60 + int(m[7] or 0) / 3600
        return t, -lat if m[4] == "S" else lat, -lon if m[8] == "W" else lon
    raise ValueError(f"Unknown aerodrome or position: {token!r}")
