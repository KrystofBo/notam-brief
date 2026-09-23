"""Spoken summary: the model condenses the HIGH and MEDIUM items for the ear and ElevenLabs reads them out."""
import re

import requests

from . import config, llm

PROMPT = (config.PROMPTS / "voice_prompt.md").read_text(encoding="utf-8")
VOICE_ID = "keLVje3aBMuRpxuu0bqO"
VOICE_MODEL = "eleven_multilingual_v2"
NUMBER = re.compile(r"\d+(?:\.\d+)?")


def _numbers(text):
    return set(NUMBER.findall(text.replace(",", "")))


def schema(ids):
    sentence = {"type": "object",
                "properties": {"ids": {"type": "array", "items": {"type": "string", "enum": list(ids)}},
                               "text": {"type": "string"}},
                "required": ["ids", "text"], "additionalProperties": False}
    return {"type": "object", "properties": {"sentences": {"type": "array", "items": sentence}},
            "required": ["sentences"], "additionalProperties": False}


def script(flight, items, unassessed=0):
    """The text to read out. A sentence that states a number its NOTAMs' summaries do not contain is replaced
    by those summaries, and a NOTAM the model leaves out is read from its summary, so nothing is dropped or
    changed silently."""
    todo = {x["id"]: x for x in items if x.get("priority") in ("HIGH", "MEDIUM")}
    parts = []
    if todo:
        user = (f"FLIGHT: {flight['dep']} {flight['dep_name']} to {flight['dest']} {flight['dest_name']}\n\nNOTAMS\n"
                + "\n".join(f"{x['priority']} {i} ({x['location']}): {x['summary']}" for i, x in todo.items()))
        res = llm.chat(config.DEFAULT_MODEL, [{"role": "system", "content": PROMPT}, {"role": "user", "content": user}],
                       {"type": "json_schema", "json_schema": {"name": "voice", "schema": schema(todo), "strict": True}},
                       max_tokens=2000, reasoning_effort=config.REASONING_EFFORT)
        try:
            sentences = llm.parse_json(res["content"])["sentences"]
        except (ValueError, KeyError, TypeError):
            sentences = []
        said = set()
        for s in sentences:
            ids = [i for i in s.get("ids") or [] if i in todo]
            text = str(s.get("text") or "").strip()
            if not ids or not text:
                continue
            source = " ".join(todo[i]["summary"] for i in ids)
            parts.append(text if _numbers(text) <= _numbers(source) else source)
            said.update(ids)
        parts += [x["summary"] for i, x in todo.items() if i not in said]
    else:
        parts.append("No high or medium priority NOTAMs for this flight.")
    if unassessed:
        parts.append(f"{unassessed} NOTAM{'s were' if unassessed > 1 else ' was'} not assessed. Read "
                     f"{'them' if unassessed > 1 else 'it'} on screen.")
    return " ".join(parts)


def speak(text):
    """MP3 of the text, read by ElevenLabs."""
    r = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}",
                      headers={"xi-api-key": config.env("ELEVENLABS_API_KEY")},
                      json={"text": text, "model_id": VOICE_MODEL}, timeout=120)
    if r.status_code >= 400:
        raise RuntimeError(f"ElevenLabs HTTP {r.status_code}: {r.text[:300]}")
    return r.content
