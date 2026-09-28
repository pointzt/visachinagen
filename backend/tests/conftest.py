import json
import os
import sys

import cv2
import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.pipeline import face_analysis as fa  # noqa: E402
from app.pipeline.spec import load_spec  # noqa: E402


@pytest.fixture(scope="session")
def spec():
    return load_spec("CHINA_VISA")


@pytest.fixture(scope="session")
def policy(spec):
    return spec["policy"]


def make_face(cx=200.0, eye_y=200.0, face_width=150.0, roll_deg=0.0, image_size=(400, 560),
              confidence=0.95, face_count=1, secondary=0.0, blend=None) -> fa.FaceAnalysis:
    """A synthetic FaceAnalysis with MediaPipe-indexed landmarks on an upright oval face.

    Proportions follow the calibration set: forehead landmark 0.62 fw above the eyes, chin
    0.95 fw below them, inter-eye 0.42 fw.
    """
    pts = np.zeros((478, 2))
    fh = face_width * 1.57  # forehead-to-chin
    top, bottom = eye_y - 0.62 * face_width, eye_y + 0.95 * face_width
    cy, ry, rx = (top + bottom) / 2, fh / 2, face_width / 2
    for i, idx in enumerate(fa.FACE_OVAL):
        t = 2 * np.pi * i / len(fa.FACE_OVAL) - np.pi / 2
        pts[idx] = (cx + rx * np.cos(t), cy + ry * np.sin(t))
    pts[fa.FOREHEAD_TOP] = (cx, top)
    pts[fa.CHIN] = (cx, bottom)
    pts[fa.CHEEK_EXTREMES[0]] = (cx - rx, eye_y + 0.1 * face_width)
    pts[fa.CHEEK_EXTREMES[1]] = (cx + rx, eye_y + 0.1 * face_width)
    pts[468] = (cx - 0.21 * face_width, eye_y)
    pts[473] = (cx + 0.21 * face_width, eye_y)
    pts[fa.NOSE_TIP] = (cx, eye_y + 0.4 * face_width)
    pts[151] = (cx, eye_y - 0.4 * face_width)
    pts[101] = (cx - 0.22 * face_width, eye_y + 0.3 * face_width)
    pts[330] = (cx + 0.22 * face_width, eye_y + 0.3 * face_width)
    if roll_deg:
        m = cv2.getRotationMatrix2D((cx, eye_y), -roll_deg, 1.0)
        pts = np.hstack([pts, np.ones((478, 1))]) @ m.T
    a, b = pts[468], pts[473]
    return fa.FaceAnalysis(
        image_size=image_size, landmarks=pts, left_eye=a, right_eye=b,
        eye_roll_deg=fa.eye_roll(a, b), yaw_deg=0.0, pitch_deg=0.0, roll_deg=roll_deg,
        blendshapes=blend or {}, confidence=confidence, face_count=face_count, secondary_face_ratio=secondary,
    )


def head_mask(face: fa.FaceAnalysis, shape, hair_ratio=1.40, shoulders=True) -> np.ndarray:
    """Boolean person mask: head ellipse from the silhouette crown to the chin plus shoulders."""
    h, w = shape
    mask = np.zeros(shape, np.uint8)
    chin = face.chin
    crown_y = chin[1] - (chin[1] - face.forehead_top[1]) * hair_ratio
    cy = (crown_y + chin[1]) / 2
    cv2.ellipse(mask, (int(face.center_x), int(cy)), (int(face.face_width * 0.56), int((chin[1] - crown_y) / 2)),
                0, 0, 360, 1, -1)
    if shoulders:
        top = int(chin[1] - 0.1 * face.face_width)
        cv2.rectangle(mask, (int(face.center_x - 0.25 * face.face_width), top),
                      (int(face.center_x + 0.25 * face.face_width), h), 1, -1)
        cv2.ellipse(mask, (int(face.center_x), int(chin[1] + 0.9 * face.face_width)),
                    (int(face.face_width * 1.6), int(face.face_width * 0.7)), 0, 180, 360, 1, -1)
        mask[int(chin[1] + 0.9 * face.face_width):] = 0
        cv2.rectangle(mask, (int(face.center_x - 1.6 * face.face_width), int(chin[1] + 0.9 * face.face_width)),
                      (int(face.center_x + 1.6 * face.face_width), h), 1, -1)
    return mask.astype(bool)


@pytest.fixture
def face_factory():
    return make_face


@pytest.fixture
def mask_factory():
    return head_mask


# --- Model-backed tests -----------------------------------------------------------------

FACES_DIR = os.environ.get("PHOTOGEN_TEST_FACES", "")


def models_ready() -> bool:
    try:
        from app.pipeline.models import models_available
        return all(models_available().values())
    except Exception:
        return False


def pytest_collection_modifyitems(config, items):
    skip_models = pytest.mark.skip(reason="MediaPipe models not available (see backend/README.md)")
    skip_faces = pytest.mark.skip(reason="Set PHOTOGEN_TEST_FACES to a folder produced by scripts/fetch_test_faces.py")
    ready = models_ready()
    faces_ok = bool(FACES_DIR) and os.path.exists(os.path.join(FACES_DIR, "manifest.json"))
    for item in items:
        if "models" in item.keywords and not ready:
            item.add_marker(skip_models)
        if "faces" in item.keywords and not faces_ok:
            item.add_marker(skip_faces)


@pytest.fixture(scope="session")
def face_manifest():
    with open(os.path.join(FACES_DIR, "manifest.json")) as f:
        return json.load(f)
