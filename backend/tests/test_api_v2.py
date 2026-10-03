import io
import json

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.pipeline import face_analysis

client = TestClient(app)


def jpeg_bytes():
    buf = io.BytesIO()
    Image.fromarray(np.full((400, 300, 3), 180, np.uint8)).save(buf, format="JPEG")
    return buf.getvalue()


def test_spec_endpoint_exposes_versioned_spec():
    r = client.get("/api/v2/spec/china_visa")
    assert r.status_code == 200
    body = r.json()
    assert body["spec"]["version"] == "1.0.0"
    assert body["rendered_profiles"]["digital"] == {"width_px": 420, "height_px": 560, "dpi": 300,
                                                   "min_kb": 40, "max_kb": 120}
    assert body["rendered_profiles"]["paper"]["width_px"] == 390


def test_unknown_spec_is_404():
    assert client.get("/api/v2/spec/atlantis").status_code == 404


def test_process_without_face_returns_retake(monkeypatch):
    monkeypatch.setattr(face_analysis, "analyze_face", lambda rgb: None)
    r = client.post("/api/v2/process", files={"file": ("a.jpg", jpeg_bytes(), "image/jpeg")},
                    data={"profile": "digital", "overrides": "{}"})
    assert r.status_code == 200
    body = r.json()
    assert body["decision"] == "retake"
    assert body["original_preview"]


def test_bad_overrides_are_rejected():
    r = client.post("/api/v2/process", files={"file": ("a.jpg", jpeg_bytes(), "image/jpeg")},
                    data={"overrides": "[1,2]"})
    assert r.status_code == 400
    r = client.post("/api/v2/process", files={"file": ("a.jpg", jpeg_bytes(), "image/jpeg")},
                    data={"overrides": json.dumps({"rotation": "sideways"})})
    assert r.status_code == 400


def test_corrupt_image_is_rejected():
    r = client.post("/api/v2/process", files={"file": ("a.jpg", b"not an image", "image/jpeg")})
    assert r.status_code == 400


def test_unknown_profile_is_rejected(monkeypatch):
    r = client.post("/api/v2/process", files={"file": ("a.jpg", jpeg_bytes(), "image/jpeg")},
                    data={"profile": "poster"})
    assert r.status_code == 400


def test_only_china_visa_endpoints_registered():
    paths = {route.path for route in app.routes}
    assert "/api/v2/process" in paths
    assert "/api/process" not in paths
