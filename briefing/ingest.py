"""Fetch and parse the notaminfo.com Pre-flight Information Bulletins.

The bulletins are EAD-derived and explicitly not official documents. Production would take
data from EUROCONTROL EAD directly or through a licensed provider.

    python -m briefing.ingest --snapshot   # freeze today's live bulletins into data/snapshots/<date>/
"""
import argparse
import html
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from .config import CACHE, SNAPSHOTS

UTC = timezone.utc
URL = "https://notaminfo.com/latest?country={}"
COUNTRIES = {"NL": "Netherlands", "DE": "Germany"}
# The site's firewall (mod_security) rejects clients that don't look like a browser.
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}
TOKENS = re.compile(r"<h([234])[^>]*>(.*?)</h\1>|<table style=\"width: 100%;background-color:#d69fac\" >(.*?)</table>", re.S)
SECTIONS = ("En-Route Information", "Nav Warnings", "Aerodromes")


def _decode(raw):
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:  # aerodrome names are sometimes Latin-1
        return raw.decode("cp1252", errors="replace")


def fetch(country, max_age_s=3 * 3600):
    """Live bulletin HTML for NL or DE, cached for a few hours (the source refreshes daily)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{country.lower()}_pib.html"
    if path.exists() and time.time() - path.stat().st_mtime < max_age_s:
        return _decode(path.read_bytes())
    r = requests.get(URL.format(COUNTRIES[country]), headers=HEADERS, timeout=60)
    r.raise_for_status()
    if b"Pre-flight Information Bulletin" not in r.content:
        raise RuntimeError(f"notaminfo.com returned no bulletin for {country} (blocked?)")
    path.write_bytes(r.content)
    return _decode(r.content)


def _clean(s):
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s).strip()


def _coord(q):
    m = re.match(r"(\d{2})(\d{2})([NS])(\d{3})(\d{2})([EW])(\d{3})", q)
    if not m:
        return None, None, None
    lat = int(m[1]) + int(m[2]) / 60
    lon = int(m[4]) + int(m[5]) / 60
    return (-lat if m[3] == "S" else lat), (-lon if m[6] == "W" else lon), int(m[7])


def _time(t):
    m = re.match(r"(\d{2})/(\d{2})/(\d{2}) (\d{2}):(\d{2})", (t or "").strip())
    return datetime(2000 + int(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[5]), tzinfo=UTC) if m else None


def parse(text, country):
    """Return (bulletin metadata, NOTAMs in bulletin order)."""
    title = re.search(r"<h[234][^>]*>(Pre-flight Information Bulletin.*?)</h[234]>", text)
    title = _clean(title.group(1)) if title else f"{country} bulletin"
    m = re.search(r"(\d{4}-\d{2}-\d{2}) at (\d{2}:\d{2}) UTC", title)
    meta = {"country": country, "title": title,
            "generated": datetime.strptime(" ".join(m.groups()), "%Y-%m-%d %H:%M").replace(tzinfo=UTC) if m else None}
    out, fir, section, aerodrome = [], None, None, None
    for tok in TOKENS.finditer(text):
        if tok.group(2) is not None:
            h = _clean(tok.group(2))
            if re.search(r"\bFIR\b", h):
                fir, section, aerodrome = h, None, None
            elif h in SECTIONS:
                section, aerodrome = h, None
            elif re.match(r"[A-Z]{4} \(", h):
                aerodrome = h
            continue
        rows = [r for r in (_clean(r) for r in re.findall(r"<td[^>]*>(.*?)</td>", tok.group(3), re.S)) if r]
        n = {"id": rows[0], "country": country, "fir": fir, "section": section, "aerodrome": aerodrome,
             "raw": "\n".join(rows), "a": [], "e": ""}
        text_rows = []
        for r in rows[1:]:
            if r.startswith("Q)"):
                n["q"] = r[2:].strip()
            elif r.startswith("A)"):
                ma = re.match(r"A\)\s*(.*?)\s+B\)\s*FROM:\s*(.*?)\s+TO:\s*(.*)$", r)
                if ma:
                    n["a"] = re.findall(r"\b[A-Z]{4}\b", ma[1])
                    n["b"], n["c"] = ma[2], ma[3]
            elif r.startswith(("LOWER:", "UPPER:", "SCHEDULE:")):
                k, v = r.split(":", 1)
                n[k.lower()] = v.strip()
            else:
                text_rows.append(r)
        n["e"] = re.sub(r"^E\)\s*", "", "\n".join(text_rows))
        q = n.get("q", "").split("/")
        if len(q) >= 8:
            n.update(q_fir=q[0], q_code=q[1], traffic=q[2], purpose=q[3], scope=q[4],
                     lower_fl=int(q[5]), upper_fl=int(q[6]))
            n["lat"], n["lon"], n["radius_nm"] = _coord(q[7])
        n["valid_from"], n["valid_to"] = _time(n.get("b")), _time(n.get("c"))
        out.append(n)
    return meta, out


def load(source="live"):
    """NL + DE NOTAMs, de-duplicated. source is 'live', a snapshot name (e.g. '2026-09-22') or a directory."""
    notams, bulletins, seen = [], [], set()
    for country in COUNTRIES:
        if source == "live":
            text = fetch(country)
        else:
            d = Path(source) if Path(source).is_dir() else SNAPSHOTS / source
            text = _decode((d / f"{country.lower()}_pib.html").read_bytes())
        meta, items = parse(text, country)
        meta["count"] = len(items)
        bulletins.append(meta)
        for n in items:
            if n["id"] not in seen:
                seen.add(n["id"])
                notams.append(n)
    return notams, bulletins


def snapshots():
    return sorted((p.name for p in SNAPSHOTS.iterdir() if p.is_dir()), reverse=True) if SNAPSHOTS.exists() else []


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snapshot", action="store_true", help="save the live bulletins as a dated snapshot")
    args = ap.parse_args()
    notams, bulletins = load("live")
    for b in bulletins:
        print(f"{b['title']}: {b['count']} NOTAMs")
    print(f"{len(notams)} unique")
    if args.snapshot:
        day = min(b["generated"] for b in bulletins).strftime("%Y-%m-%d")
        d = SNAPSHOTS / day
        d.mkdir(parents=True, exist_ok=True)
        for c in COUNTRIES:
            (d / f"{c.lower()}_pib.html").write_bytes((CACHE / f"{c.lower()}_pib.html").read_bytes())
        print(f"saved snapshot {d}")


if __name__ == "__main__":
    main()
