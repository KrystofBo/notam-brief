"""Demo web app.

    uvicorn app:app --port 8765
"""
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from briefing import aerodromes, config, ingest, llm, pipeline

STATIC = Path(__file__).parent / "static"
app = FastAPI(title="VFR NOTAM briefing")


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


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/meta")
def meta():
    cfg = pipeline.eval_routes()
    return {
        "default_model": config.DEFAULT_MODEL,
        "snapshots": ingest.snapshots(),
        "eval": {"snapshot": cfg["snapshot"], "window": cfg["window"]},
        "routes": [{k: r.get(k) for k in ("id", "name", "dep", "dest", "via", "why")} for r in cfg["routes"]],
        "aerodromes": [[a["icao"], a["name"]] for a in aerodromes.table().values()],
    }


@app.get("/api/models")
def models():
    try:
        return {"models": sorted(llm.models_info())}
    except Exception as e:
        return {"models": [config.DEFAULT_MODEL], "error": str(e)}


@app.post("/api/brief")
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
