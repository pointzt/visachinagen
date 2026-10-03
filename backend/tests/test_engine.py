"""End-to-end tests on real faces. Need MediaPipe models and PHOTOGEN_TEST_FACES."""

import base64
import io
import os

import cv2
import numpy as np
import pytest
from PIL import Image

from app.pipeline.cache import ensure_matte
from app.pipeline.engine import process
from conftest import FACES_DIR

pytestmark = [pytest.mark.models, pytest.mark.faces]


def load(face_id):
    path = os.path.join(FACES_DIR, f"{face_id}.jpg")
    with open(path, "rb") as f:
        return f.read(), ensure_matte(path)


def png(rgb):
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="PNG")
    return buf.getvalue()


def checks(result):
    return {c["id"]: c for c in result["checks"]}


def test_output_file_meets_digital_file_rules():
    image, matte = load("f15")
    r = process(image, "digital", None, matte)
    data = base64.b64decode(r["processed_image"])
    img = Image.open(io.BytesIO(data))
    assert img.format == "JPEG" and img.size == (420, 560) and img.mode == "RGB"
    assert 40 * 1024 <= len(data) <= 120 * 1024
    assert round(img.info["dpi"][0]) == 300
    assert len(img.getexif()) == 0
    c = checks(r)
    for cid in ("out.dimensions", "out.file_size", "out.format", "out.crown_to_top", "out.eye_line",
                "out.face_width", "out.inter_eye", "out.centered", "out.background_color", "out.no_border"):
        assert c[cid]["status"] == "pass", (cid, c[cid])
    assert r["spec"]["version"] == "1.0.0"
    assert r["output"]["file_size_kb"] == pytest.approx(len(data) / 1024, abs=0.1)


def test_paper_profile_dimensions_and_head_height():
    image, matte = load("f19")
    r = process(image, "paper", None, matte)
    c = checks(r)
    assert Image.open(io.BytesIO(base64.b64decode(r["processed_image"]))).size == (390, 567)
    for cid in ("out.head_height", "out.crown_to_top", "out.chin_to_bottom"):
        assert c[cid]["status"] == "pass", (cid, c[cid])


def test_no_face_recommends_retake():
    blank = np.full((800, 600, 3), 200, np.uint8)
    r = process(png(blank), "digital")
    assert r["decision"] == "retake"
    assert r["processed_image"] is None
    assert r["retake_advice"]


def test_two_people_are_rejected():
    a, ma = load("f19")
    b, mb = load("f20")
    ia, ib = np.array(Image.open(io.BytesIO(a)).convert("RGB")), np.array(Image.open(io.BytesIO(b)).convert("RGB"))
    h = min(ia.shape[0], ib.shape[0])
    both = np.hstack([ia[:h], ib[:h]])
    alpha = np.hstack([np.array(Image.open(io.BytesIO(ma)))[:h], np.array(Image.open(io.BytesIO(mb)))[:h]])
    r = process(png(both), "digital", None, png(alpha))
    assert checks(r)["in.single_person"]["status"] == "fail"
    assert r["decision"] == "retake"


def test_blurred_dark_photo_is_not_passed():
    image, matte = load("f19")
    rgb = np.array(Image.open(io.BytesIO(image)).convert("RGB"))
    bad = (cv2.GaussianBlur(rgb, (0, 0), 6) * 0.35).astype(np.uint8)
    r = process(png(bad), "digital", None, matte)
    assert r["decision"] != "pass"
    c = checks(r)
    flagged = [k for k in ("in.sharpness", "in.face_confidence", "in.exposure") if k in c and c[k]["status"] != "pass"]
    assert flagged
    # The whole frame is dark, so a bounded exposure lift is applied and reported.
    light = next(x for x in r["corrections"] if x["id"] == "lighting")
    assert light["applied"] and 0 < light["exposure_ev"] <= 0.5


def test_manual_rotation_is_rigid_and_geometry_is_recomputed():
    image, matte = load("f19")
    rgb = np.array(Image.open(io.BytesIO(image)).convert("RGB"))
    alpha = np.array(Image.open(io.BytesIO(matte)))
    h, w = alpha.shape
    m = cv2.getRotationMatrix2D((w / 2, h / 2), -6, 1.0)  # camera rolled 6° clockwise
    tilted = cv2.warpAffine(rgb, m, (w, h), borderMode=cv2.BORDER_REPLICATE)
    tilted_alpha = cv2.warpAffine(alpha, m, (w, h))
    auto = process(png(tilted), "digital", None, png(tilted_alpha))
    rot = next(x for x in auto["corrections"] if x["id"] == "rotation")
    assert rot["classification"] in ("camera_tilt", "ambiguous")
    assert rot["suggested"] or rot["applied"]
    fixed = process(png(tilted), "digital", {"rotation": "manual", "rotation_deg": rot["suggested_angle_deg"]},
                    png(tilted_alpha))
    c = checks(fixed)
    assert abs(c["out.pose_roll"]["measured"]) < 1.5
    for cid in ("out.crown_to_top", "out.eye_line", "out.face_width", "out.centered"):
        assert c[cid]["status"] == "pass", (cid, c[cid])


def test_tilted_head_is_straightened_automatically():
    image, matte = load("f08")  # eye line tilted about -6°
    r = process(image, "digital", None, matte)
    rot = next(x for x in r["corrections"] if x["id"] == "rotation")
    assert rot["applied"] and rot["mode"] == "auto"
    c = checks(r)
    assert c["in.head_tilt"]["status"] == "pass"
    assert abs(c["out.pose_roll"]["measured"]) < 1.5


def test_rotation_can_be_turned_off():
    image, matte = load("f08")  # eye line tilted about -6°
    r = process(image, "digital", {"rotation": "off"}, matte)
    rot = next(x for x in r["corrections"] if x["id"] == "rotation")
    assert not rot["applied"] and rot["angle_deg"] == 0


def test_rerender_with_returned_matte_is_deterministic():
    image, _ = load("f15")
    first = process(image, "digital", None, ensure_matte(os.path.join(FACES_DIR, "f15.jpg")))
    again = process(image, "digital", None, base64.b64decode(first["alpha_png"]))
    assert first["processed_image"] == again["processed_image"]


def test_overrides_are_reflected_in_corrections():
    image, matte = load("f15")
    r = process(image, "digital", {"replace_background": False, "lighting": "off", "crop": {"scale": 1.05}}, matte)
    corr = {c["id"]: c for c in r["corrections"]}
    assert corr["background"]["applied"] is False
    assert corr["lighting"]["applied"] is False
    assert corr["crop"]["manual"] is True
    assert "bg.kept_white" in checks(r)


def test_decision_reflects_expression_warning():
    image, matte = load("f19")  # smiling
    r = process(image, "digital", None, matte)
    assert checks(r)["in.neutral"]["status"] == "warn"
    assert r["decision"] == "review"


def test_every_check_is_labelled_with_its_basis():
    image, matte = load("f15")
    r = process(image, "digital", None, matte)
    for c in r["checks"]:
        assert c["basis"] in ("verified", "provisional")
        assert c["status"] in ("pass", "warn", "fail", "unverifiable")
        assert c["stage"] in ("input", "output")
