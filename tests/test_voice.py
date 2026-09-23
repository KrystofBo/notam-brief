"""Spoken summary with a fake model: which items are read, and the fallbacks that stop a NOTAM being dropped or a
number being changed."""
import json

import pytest

from briefing import voice

FLIGHT = {"dep": "EHLE", "dep_name": "Lelystad", "dest": "EHHV", "dest_name": "Hilversum"}
ITEMS = [{"id": "A0001/26", "priority": "HIGH", "location": "EHHV", "summary": "Runway 18/36 is 620 m long."},
         {"id": "A0002/26", "priority": "MEDIUM", "location": "EHLE", "summary": "Crane 160 ft AMSL near runway 05."},
         {"id": "A0003/26", "priority": "LOW", "location": "EHLE", "summary": "New phone number."}]


def fake_model(monkeypatch, sentences):
    seen = []

    def chat(model, messages, response_format=None, **kw):
        seen.append(messages[1]["content"])
        return {"content": json.dumps({"sentences": sentences}), "finish": "stop", "usage": {}, "latency_s": 0}

    monkeypatch.setattr(voice.llm, "chat", chat)
    return seen


def test_reads_high_and_medium_items_only(monkeypatch):
    seen = fake_model(monkeypatch, [{"ids": ["A0001/26"], "text": "Hilversum runway 18/36, 620 metres."},
                                    {"ids": ["A0002/26"], "text": "Lelystad crane, 160 feet above sea level."}])
    assert voice.script(FLIGHT, ITEMS) == "Hilversum runway 18/36, 620 metres. Lelystad crane, 160 feet above sea level."
    assert "A0001/26" in seen[0] and "A0002/26" in seen[0] and "A0003/26" not in seen[0]


def test_changed_number_and_skipped_item_fall_back_to_the_summary(monkeypatch):
    fake_model(monkeypatch, [{"ids": ["A0001/26"], "text": "Hilversum runway 18/36, 600 metres."}])
    assert voice.script(FLIGHT, ITEMS) == "Runway 18/36 is 620 m long. Crane 160 ft AMSL near runway 05."


@pytest.mark.parametrize("text, spoken", [
    ("runway 18/36 is 620 meters", "runway one eight, three six is six two zero metres"),
    ("Runway 09L and 27R", "Runway zero niner left and two seven right"),
    ("near runway 06 and 24", "near runway zero six and two four"),
    ("taxiway N between A2 and N1, including N2 and apron L, is closed",
     "taxiway November between Alfa two and November one, including November two and apron Lima, is closed"),
    ("up to flight level 150, not FL100", "up to flight level one five zero, not flight level one hundred"),
    ("on 124.300 MHz or 118.005", "on one two four decimal three or one one eight decimal zero zero five"),
    ("from 0600 to 1800 UTC", "from zero six zero zero to one eight zero zero UTC"),
    ("active 0700 to 0900Z", "active zero seven zero zero to zero niner zero zero UTC"),
    ("from 10:00Z to 15:00Z", "from one zero zero zero UTC to one five zero zero UTC"),
    ("open 05:30-19:00, PPR between 19:00-20:00", "open zero five three zero to one niner zero zero, "
     "PPR between one niner zero zero and two zero zero zero"),
    ("on 124.300 megahertz", "on one two four decimal three"),
    ("below 1500 feet, top 968 feet above sea level, 400 ft, 11000 feet",
     "below one thousand five hundred feet, top niner six eight feet above sea level, four hundred feet, "
     "one one thousand feet"),
    ("445 meters, 3.15 miles, radius 1 nm, 5 NM", "four four five metres, three decimal one five miles, "
     "radius one mile, five miles"),
    ("between Rotterdam and EHSE, ELEV", "between Rotterdam and Echo Hotel Sierra Echo, ELEV"),
    ("A drone operates near Eemshaven. 2 NOTAMs were not assessed, PPR 48 hours ahead on 23 Sep.",
     "A drone operates near Eemshaven. 2 NOTAMs were not assessed, PPR 48 hours ahead on 23 Sep."),
])
def test_phraseology(text, spoken):
    assert voice.phraseology(text) == spoken


def test_nothing_to_read_and_unassessed(monkeypatch):
    monkeypatch.setattr(voice.llm, "chat", lambda *a, **k: pytest.fail("no model call expected"))
    assert voice.script(FLIGHT, ITEMS[2:], unassessed=2) == \
        "No high or medium priority NOTAMs for this flight. 2 NOTAMs were not assessed. Read them on screen."
