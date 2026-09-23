"""API input limits: the NOTAM data is never read from a path the caller chooses, and one voice request cannot run up
ElevenLabs costs."""
import pytest
from fastapi import HTTPException

import app as web
from briefing import voice


@pytest.mark.parametrize("source", ["..", "../..", "/etc", "C:\\Windows", "2026-09-22/../.."])
def test_brief_accepts_only_live_or_a_snapshot(source):
    with pytest.raises(HTTPException) as e:
        web.brief(web.BriefRequest(dep="EHLE", dest="EHHV", source=source))
    assert e.value.status_code == 400


def test_speak_refuses_long_text_before_calling_elevenlabs(monkeypatch):
    monkeypatch.setattr(voice.requests, "post", lambda *a, **k: pytest.fail("ElevenLabs must not be called"))
    with pytest.raises(ValueError):
        voice.speak("x" * (voice.MAX_CHARS + 1))


def test_voice_request_is_limited_to_100_items():
    with pytest.raises(ValueError):  # pydantic's ValidationError is a ValueError
        web.VoiceRequest(flight={}, items=[{}] * 101)
