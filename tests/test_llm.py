"""Model-stage contract with a fake API: order, missing items, broken JSON and priorities."""
import json

import pytest

from briefing import llm

NOTAMS = [{"id": f"A{i:04d}/26", "raw": f"A{i:04d}/26\nE) TEST {i}"} for i in range(6)]


def reply(items, weather="", finish="stop"):
    return {"content": json.dumps({"weather_summary": weather, "items": items}), "finish": finish,
            "usage": {"prompt_tokens": 100, "completion_tokens": 10}, "latency_s": 0.01}


def item(i, relevant=True, priority="HIGH"):
    return {"id": NOTAMS[i]["id"], "relevant": relevant, "priority": priority if relevant else None,
            "reason": f"r{i}", "summary": f"s{i}" if relevant else ""}


@pytest.fixture(autouse=True)
def no_pricing_lookup(monkeypatch):
    monkeypatch.setattr(llm, "models_info", lambda: {})


def test_order_missing_and_priority(monkeypatch):
    # Reversed order, one NOTAM missing, one relevant without a valid priority, one unknown id.
    items = [item(5), item(4, False), item(3, True, "URGENT"), item(1), item(0, False),
             {"id": "X9999/26", "relevant": True, "priority": "HIGH", "reason": "", "summary": ""}]
    monkeypatch.setattr(llm, "chat", lambda *a, **k: reply(items, "VFR"))
    out = llm.assess("m", "FLIGHT", "WX", NOTAMS)
    assert [x["id"] for x in out["items"]] == [n["id"] for n in NOTAMS]
    by = {x["id"]: x for x in out["items"]}
    assert by["A0002/26"]["assessed"] is False                       # missing -> surfaced, not dropped
    assert by["A0003/26"]["priority"] == "LOW"                       # relevant, bad priority -> LOW
    assert by["A0004/26"]["priority"] is None and by["A0004/26"]["summary"] == ""
    assert out["weather_summary"] == "VFR"


def test_invalid_json_splits_chunk(monkeypatch):
    calls = []

    def fake(model, messages, response_format=None, **kw):
        user = messages[1]["content"]
        ids = [n["id"] for n in NOTAMS if n["id"] in user]
        calls.append(ids)
        if len(ids) > 3:
            return {"content": '{"items": [', "finish": "length", "usage": {}, "latency_s": 0}
        return reply([item(int(i[1:5])) for i in ids])

    monkeypatch.setattr(llm, "chat", fake)
    out = llm.assess("m", "FLIGHT", "", NOTAMS)
    assert all(x["assessed"] and x["relevant"] for x in out["items"])
    assert len(calls) == 3 and out["errors"]


def test_chunking_and_cost(monkeypatch):
    monkeypatch.setattr(llm, "chat", lambda m, msgs, *a, **k: reply(
        [item(int(i[1:5]), False) for i in [n["id"] for n in NOTAMS if n["id"] in msgs[1]["content"]]]))
    monkeypatch.setitem(llm.config.PRICES, "m", (1.0, 2.0))
    out = llm.assess("m", "FLIGHT", "", NOTAMS, chunk_size=2)
    assert out["calls"] == 3
    assert out["usage"] == {"prompt_tokens": 300, "completion_tokens": 30}
    assert out["cost_usd"] == pytest.approx((300 * 1.0 + 30 * 2.0) / 1e6)


def test_schema_pins_ids_and_count():
    s = llm.schema(["A0001/26", "A0002/26"])
    items = s["properties"]["items"]
    assert items["minItems"] == items["maxItems"] == 2
    assert items["items"]["properties"]["id"]["enum"] == ["A0001/26", "A0002/26"]


def test_parse_json_tolerates_fences_and_thinking():
    assert llm.parse_json('<think>hmm</think>\n```json\n{"a": 1}\n```') == {"a": 1}
    assert llm.parse_json('Here you go: {"a": 2} done') == {"a": 2}


def test_falls_back_through_response_formats(monkeypatch):
    seen = []

    def fake(model, messages, response_format=None, **kw):
        seen.append(response_format)
        js = response_format.get("json_schema") or {}
        if response_format["type"] == "json_schema" and "schema" in js:
            raise llm.LLMError("HTTP 400: bad json_schema")  # only accepts the bare schema
        return reply([item(i, False) for i in range(len(NOTAMS))])

    monkeypatch.setattr(llm, "chat", fake)
    monkeypatch.setattr(llm, "FORMAT_OK", {})
    assert all(x["assessed"] for x in llm.assess("m", "F", "", NOTAMS)["items"])
    assert "schema" not in seen[1]["json_schema"] and llm.FORMAT_OK["m"] == 1
    llm.assess("m", "F", "", NOTAMS)
    assert len(seen) == 3  # the second briefing goes straight to the working format
