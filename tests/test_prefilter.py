"""Route geometry used by the pre-filter and passed to the model."""
import pytest

from briefing import ingest, prefilter
from briefing.pipeline import eval_routes, make_flight

NORTH = [(52.0, 5.0), (53.0, 5.0)]  # 60 nm due north


@pytest.mark.parametrize("lat, lon, side, where", [
    (52.5, 5.1, "right", "abeam"),   # east of a northbound track
    (52.5, 4.9, "left", "abeam"),
    (51.9, 5.0, "right", "start"),   # behind the departure point
    (53.1, 5.0, "right", "end"),
])
def test_route_position(lat, lon, side, where):
    d, along, s, w = prefilter.route_position(lat, lon, NORTH)
    assert w == where
    if where == "abeam":
        assert s == side and along == pytest.approx(30, abs=0.1) and d == pytest.approx(3.7, abs=0.1)


def test_distance_unchanged():
    assert prefilter.dist_to_path_nm(52.5, 5.1, NORTH) == prefilter.route_position(52.5, 5.1, NORTH)[0]


@pytest.fixture(scope="module")
def snapshot():
    cfg = eval_routes()
    return cfg, ingest.load(cfg["snapshot"])[0]


def geometry_for(snapshot, route_id, notam_id):
    cfg, notams = snapshot
    r = next(r for r in cfg["routes"] if r["id"] == route_id)
    f = make_flight(r["dep"], r["dest"], path=r["path"], window=cfg["window"], alt_ft=cfg["alt_ft"],
                    band_fl=tuple(cfg["band_fl"]), corridor_nm=cfg["corridor_nm"])
    n = next(n for n in prefilter.candidates(notams, f) if n["id"] == notam_id)
    return prefilter.geometry(n, f)


def test_geometry_on_snapshot(snapshot):
    assert geometry_for(snapshot, 2, "B0903/26") == "at the destination aerodrome EHHO"
    g = geometry_for(snapshot, 4, "F2313/26")  # wind farm near Steinfurt, right under the Twente-Muenster track
    assert g.startswith("circle centre on the track") and "the route passes through the circle" in g
    g = geometry_for(snapshot, 4, "F2633/26")  # wind turbine near Heek, south of the eastbound track
    assert "nm right of the track" in g and "passes through" not in g
