"""Demo web app.

    uvicorn app:app --port 8765
"""
import base64
import os
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from google.auth import exceptions as google_exceptions
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from pydantic import BaseModel

from briefing import aerodromes, config, ingest, llm, pipeline, voice

STATIC = Path(__file__).parent / "static"
app = FastAPI(title="VFR NOTAM briefing")


def signed_in(authorization: str = Header(default="")):
    """Email of the signed-in user. With a Firebase project configured (FIREBASE_PROJECT_ID) every API call needs
    a Firebase ID token for a verified Google account listed in ALLOWED_EMAILS. On Vercel sign-in is always
    required; locally, without a project, the app stays open."""
    project = os.environ.get("FIREBASE_PROJECT_ID")
    if not project:
        if os.environ.get("VERCEL"):
            raise HTTPException(503, "Sign-in is not configured: set FIREBASE_PROJECT_ID and FIREBASE_API_KEY.")
        return None
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(401, "Sign in first.")
    try:
        claims = id_token.verify_firebase_token(token, google_requests.Request(), audience=project)
    except ValueError as e:
        raise HTTPException(401, f"Your sign-in has expired or is invalid. Sign in again. ({e})")
    except google_exceptions.GoogleAuthError as e:
        raise HTTPException(503, f"Could not check your sign-in: {e}")
    if claims.get("iss") != f"https://securetoken.google.com/{project}":
        raise HTTPException(401, "This sign-in belongs to another Firebase project.")
    email = str(claims.get("email") or "").lower()
    allowed = {e.strip().lower() for e in os.environ.get("ALLOWED_EMAILS", "").split(",") if e.strip()}
    if not claims.get("email_verified") or email not in allowed:
        raise HTTPException(403, f"{email or 'This account'} is not on the list of allowed users.")
    return email


class BriefRequest(BaseModel):
    dep: str
    dest: str
    via: str = ""
    alternate: str = ""
    dep_time: str = ""               # planned departure, UTC, e.g. 2026-09-23T09:00
    alt_ft: int = 3000
    model: str = ""
    source: str = "live"             # 'live' or a snapshot name
    prefilter: bool = True
    reasoning: bool = False          # let the model think first (slower); off sends reasoning_effort "none"
    preset: Optional[int] = None     # a labelled test route: use its exact path (and, on a snapshot, its window)


class VoiceRequest(BaseModel):
    flight: dict                     # the briefing's flight
    items: list                      # the briefing's relevant items; only HIGH and MEDIUM are read out
    unassessed: int = 0


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/config")
def client_config():
    """Public Firebase web config for the sign-in button; null when sign-in is off."""
    project = os.environ.get("FIREBASE_PROJECT_ID")
    return {"firebase": {"apiKey": os.environ.get("FIREBASE_API_KEY"), "authDomain": f"{project}.firebaseapp.com",
                         "projectId": project} if project else None}


@app.get("/api/meta", dependencies=[Depends(signed_in)])
def meta():
    cfg = pipeline.eval_routes()
    return {
        "default_model": config.DEFAULT_MODEL,
        "snapshots": ingest.snapshots(),
        "eval": {"snapshot": cfg["snapshot"], "window": cfg["window"]},
        "routes": [{k: r.get(k) for k in ("id", "name", "dep", "dest", "via", "why")} for r in cfg["routes"]],
        "aerodromes": [[a["icao"], a["name"]] for a in aerodromes.table().values()],
    }


@app.get("/api/models", dependencies=[Depends(signed_in)])
def models():
    try:
        return {"models": sorted(llm.models_info())}
    except Exception as e:
        return {"models": [config.DEFAULT_MODEL], "error": str(e)}


@app.post("/api/brief", dependencies=[Depends(signed_in)])
def brief(req: BriefRequest):
    kw = dict(via=req.via.split(), alternate=req.alternate or None, alt_ft=req.alt_ft, model=req.model or None,
              source=req.source or "live", use_prefilter=req.prefilter, reasoning="default" if req.reasoning else None)
    if req.preset:
        cfg = pipeline.eval_routes()
        route = next((r for r in cfg["routes"] if r["id"] == req.preset), None)
        if route:
            kw.update(path=route["path"], route_note=route.get("note"))
            if kw["source"] != "live":  # the labelled scenario: same window, band and corridor as the labels
                kw.update(window=cfg["window"], band_fl=tuple(cfg["band_fl"]), corridor_nm=cfg["corridor_nm"])
    if "window" not in kw:
        kw["dep_time"] = req.dep_time or None
    try:
        return pipeline.brief(req.dep, req.dest, **kw)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except llm.LLMError as e:
        raise HTTPException(502, f"Model call failed: {e}")
    except RuntimeError as e:
        raise HTTPException(500, str(e))


@app.post("/api/voice", dependencies=[Depends(signed_in)])
def voice_summary(req: VoiceRequest):
    try:
        text = voice.phraseology(voice.script(req.flight, req.items, req.unassessed))
        audio = voice.speak(text)
    except llm.LLMError as e:
        raise HTTPException(502, f"Model call failed: {e}")
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    return {"script": text, "audio": base64.b64encode(audio).decode()}
