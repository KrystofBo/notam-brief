"""The labelled snapshot must keep producing exactly the candidate sets the labels were written for."""
import csv
from collections import defaultdict

import pytest

from briefing import config, ingest, prefilter
from briefing.pipeline import eval_routes, make_flight

CFG = eval_routes()
EXPECTED = {1: 25, 2: 17, 3: 59, 4: 24, 5: 23}


@pytest.fixture(scope="module")
def notams():
    return ingest.load(CFG["snapshot"])[0]


def flight(route):
    return make_flight(route["dep"], route["dest"], path=route["path"], window=CFG["window"],
                       alt_ft=CFG["alt_ft"], band_fl=tuple(CFG["band_fl"]), corridor_nm=CFG["corridor_nm"])


def labels():
    out = defaultdict(dict)
    with open(config.EVAL / "labels_flat.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[int(r["route"])][r["notam_id"]] = r
    return out


def test_bulletin_sizes(notams):
    assert len(notams) == 945
    assert sum(n["country"] == "NL" for n in notams) == 132  # 131 EHAA + 1 EDXX item carried in the NL bulletin


@pytest.mark.parametrize("route", CFG["routes"], ids=lambda r: f"route{r['id']}")
def test_candidates_match_labels(notams, route):
    ids = [n["id"] for n in prefilter.candidates(notams, flight(route))]
    assert len(ids) == EXPECTED[route["id"]]
    assert set(ids) == set(labels()[route["id"]])


def test_parse_fields(notams):
    n = next(n for n in notams if n["id"] == "A2195/26")
    assert n["q_code"] == "QWPLW" and n["lower_fl"] == 0 and n["upper_fl"] == 150 and n["radius_nm"] == 5
    assert n["schedule"] == "0700-1800" and n["raw"].startswith("A2195/26\nQ) EHAA/QWPLW")
