"""Spoken summary: the model condenses the HIGH and MEDIUM items for the ear and ElevenLabs reads them out."""
import re

import requests

from . import aerodromes, config, llm

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


# ICAO radiotelephony (Annex 10 Vol II, 5.2.1.4 and the spelling alphabet)
DIGITS = "zero one two three four five six seven eight niner".split()
ALFA = dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "Alfa Bravo Charlie Delta Echo Foxtrot Golf Hotel India Juliett Kilo "
                "Lima Mike November Oscar Papa Quebec Romeo Sierra Tango Uniform Victor Whiskey X-ray Yankee Zulu".split()))
UNITS = {"feet": "feet", "foot": "feet", "ft": "feet", "metres": "metres", "meters": "metres", "m": "metres",
         "miles": "miles", "nm": "miles", "NM": "miles"}
ONE = {"feet": "foot", "metres": "metre", "miles": "mile"}
RWY = r"\d{2}[LRC]?(?:/\d{2}[LRC]?)?"
TWY = r"[A-Z]\d{0,2}"
LIST = r"(?:,\s*|\s+and\s+|\s+or\s+)"


def _digits(s):
    """'124.3' -> 'one two four decimal three'"""
    return " ".join("decimal" if c == "." else DIGITS[int(c)] for c in s)


def _spell(s):
    """'A2' -> 'Alfa two', 'EHSE' -> 'Echo Hotel Sierra Echo'"""
    return " ".join(ALFA.get(c) or DIGITS[int(c)] for c in s)


def _runway(d):
    """'18/36' -> 'one eight, three six', '09L' -> 'zero niner left'"""
    return ", ".join(_digits(x[:2]) + {"L": " left", "R": " right", "C": " centre"}.get(x[2:], "")
                     for x in d.split("/"))


def _amount(n):
    """Whole hundreds and thousands as such ('one thousand five hundred'), anything else digit by digit."""
    n = n.replace(",", "")
    if n.isdigit() and int(n) >= 100 and int(n) % 100 == 0:
        th, h = divmod(int(n) // 100, 10)
        return " ".join(([_digits(str(th)), "thousand"] if th else []) + ([DIGITS[h], "hundred"] if h else []))
    return _digits(n)


def _time(h, m):
    return _digits(h + m) if int(h) < 24 and int(m) < 60 else f"{h}{m}"


def _frequency(m):
    dec = m[2].ljust(3, "0")
    return _digits(f"{m[1]}.{dec[0] if dec.endswith('00') else dec}")  # the last two digits are dropped when both 0


def _flight_level(m):
    fl = int(m[2])
    return ("flight level" if m[1] == "FL" else m[1]) + " " + \
        (f"{DIGITS[fl // 100]} hundred" if fl % 100 == 0 else _digits(m[2]))


def phraseology(text):
    """The text as a pilot would hear it on the radio: designators in the spelling alphabet, numbers digit by
    digit, heights and distances in whole hundreds and thousands, frequencies with 'decimal'. Only the aviation
    designators and quantities recognised here are changed; everything else is left for the voice to read."""
    t = re.sub(r"\b(1[0-3]\d)\.(\d{1,3})(?:\s?(?:MHz|megahertz))?\b", _frequency, text)
    t = re.sub(r"\b([Ff]light level|FL)\s?(\d{2,3})\b", _flight_level, t)
    t = re.sub(rf"\b([Rr]unways?)\s+({RWY}(?:{LIST}{RWY})*)\b",
               lambda m: m[1] + " " + re.sub(RWY, lambda d: _runway(d[0]), m[2]), t)
    t = re.sub(rf"\b((?i:taxiways?|aprons?|holding points?))\s+({TWY}(?:{LIST}{TWY})*)\b",
               lambda m: m[1] + " " + re.sub(TWY, lambda d: _spell(d[0]), m[2]), t)
    t = re.sub(r"\b[A-Z]\d{1,2}\b", lambda m: _spell(m[0]), t)                  # holding points, taxiways: A2, N1
    t = re.sub(r"\bE[BDHLT][A-Z]{2}\b", lambda m: _spell(m[0]) if aerodromes.get(m[0]) else m[0], t)  # EHSE
    t = re.sub(r"\b(between\s+)?(\d{2}:?\d{2})\s*-\s*(\d{2}:?\d{2})(?!\d)",       # 0600-1800Z, 05:30-19:00
               lambda m: f"{m[1] or ''}{m[2]} {'and' if m[1] else 'to'} {m[3]}", t)
    t = re.sub(r"\b(\d{2}):?(\d{2})\s+(to|until|and)\s+(\d{2}):?(\d{2})(?:Z|\s?UTC)\b",
               lambda m: f"{_time(m[1], m[2])} {m[3]} {_time(m[4], m[5])} UTC", t)
    t = re.sub(r"\b(\d{2}):?(\d{2})(?:Z|\s?UTC)\b", lambda m: f"{_time(m[1], m[2])} UTC", t)
    t = re.sub(r"\b(\d{2}):(\d{2})\b", lambda m: _time(m[1], m[2]), t)
    return re.sub(r"\b(\d[\d,]*(?:\.\d+)?)\s?(feet|foot|ft|metres|meters|m|miles|nm|NM)\b",
                  lambda m: f"{_amount(m[1])} {ONE[UNITS[m[2]]] if m[1] == '1' else UNITS[m[2]]}", t)


def speak(text):
    """MP3 of the text, read by ElevenLabs."""
    r = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}",
                      headers={"xi-api-key": config.env("ELEVENLABS_API_KEY")},
                      json={"text": text, "model_id": VOICE_MODEL}, timeout=120)
    if r.status_code >= 400:
        raise RuntimeError(f"ElevenLabs HTTP {r.status_code}: {r.text[:300]}")
    return r.content
