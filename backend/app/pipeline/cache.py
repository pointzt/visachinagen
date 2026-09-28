"""Matte cache for tests and evaluation only (the API never stores user images)."""

import os

from app.pipeline import face_analysis, segmentation
from app.pipeline.engine import decode_image
from app.pipeline.spec import load_spec


def ensure_matte(image_path: str) -> bytes:
    """Return the PNG matte for ``image_path``, computing it next to the image on first use."""
    matte_path = os.path.splitext(image_path)[0] + ".matte.png"
    if os.path.exists(matte_path):
        with open(matte_path, "rb") as f:
            return f.read()
    with open(image_path, "rb") as f:
        rgb = decode_image(f.read(), load_spec()["policy"]["working_max_side_px"])
    alpha = segmentation.segment_person(rgb)
    face = face_analysis.analyze_face(rgb)
    if face is not None:
        alpha = segmentation.keep_main_subject(alpha, tuple(face.landmarks[face_analysis.NOSE_TIP]))
    data = segmentation.encode_alpha(alpha)
    with open(matte_path, "wb") as f:
        f.write(data)
    return data
