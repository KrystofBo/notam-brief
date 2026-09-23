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


def test_nothing_to_read_and_unassessed(monkeypatch):
    monkeypatch.setattr(voice.llm, "chat", lambda *a, **k: pytest.fail("no model call expected"))
    assert voice.script(FLIGHT, ITEMS[2:], unassessed=2) == \
        "No high or medium priority NOTAMs for this flight. 2 NOTAMs were not assessed. Read them on screen."
