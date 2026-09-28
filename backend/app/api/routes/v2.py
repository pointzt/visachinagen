"""China visa engine API (v2). The v1 /api/process endpoint is unchanged.

Endpoints are plain ``def`` so FastAPI runs the CPU-heavy work in its thread pool instead of
blocking the event loop.
"""

import json

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.pipeline import engine
from app.pipeline.models import models_available
from app.pipeline.spec import constraints_for, load_spec

router = APIRouter()

MAX_FILE_SIZE = 15 * 1024 * 1024


@router.get("/v2/spec/{spec_id}")
def get_spec(spec_id: str = "CHINA_VISA"):
    try:
        spec = load_spec(spec_id.upper())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    profiles = {}
    for name in spec["profiles"]:
        c = constraints_for(spec, name)
        profiles[name] = {"width_px": c.width, "height_px": c.height, "dpi": c.dpi,
                          "min_kb": c.min_kb, "max_kb": c.max_kb}
    return {"spec": spec, "rendered_profiles": profiles}


@router.get("/v2/health")
def health():
    return {"status": "healthy", "models": models_available()}


@router.post("/v2/process")
def process_v2(
    file: UploadFile = File(...),
    profile: str = Form(default="digital"),
    overrides: str = Form(default="{}"),
    alpha: UploadFile | None = File(default=None),
):
    """Analyse and render a photo.

    Send ``alpha`` (the ``alpha_png`` returned by a previous call, decoded to PNG bytes) to
    re-render with new ``overrides`` without re-running background segmentation.
    """
    image_bytes = file.file.read()
    if len(image_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 15MB.")
    try:
        ov = json.loads(overrides) if overrides else {}
        if not isinstance(ov, dict):
            raise ValueError
    except ValueError:
        raise HTTPException(status_code=400, detail="overrides must be a JSON object.")
    alpha_bytes = alpha.file.read() if alpha is not None else None

    try:
        return engine.process(image_bytes, profile=profile, overrides=ov, alpha_png=alpha_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except OSError:
        raise HTTPException(status_code=400, detail="Unsupported or corrupt image file.")
