import math

import numpy as np
import pytest

from app.pipeline import lighting
from app.pipeline.checks import PASS, WARN
from app.pipeline.color import rgb_to_lab


def portrait(face_factory, skin=(190, 140, 115), gain=1.0, noise=6.0, seed=0, wall=(228, 228, 224)):
    """Face on a light wall, with dark eyes and brows so the face has natural contrast.
    ``gain`` scales the whole frame, simulating camera exposure."""
    import cv2
    from app.pipeline.background_qa import face_polygon_mask
    rng = np.random.default_rng(seed)
    face = face_factory(cx=300, eye_y=380, face_width=200, image_size=(600, 900))
    img = np.empty((900, 600, 3), np.float32)
    img[...] = wall
    oval = face_polygon_mask((900, 600), face, shrink=-0.05)
    img[oval] = skin
    for x in (face.left_eye[0], face.right_eye[0]):
        cv2.ellipse(img, (int(x), int(face.eye_mid[1])), (22, 9), 0, 0, 360, (40, 30, 25), -1)
        cv2.ellipse(img, (int(x), int(face.eye_mid[1] - 30)), (30, 6), 0, 0, 360, (60, 45, 35), -1)
    img = img * gain + rng.normal(0, noise, img.shape)
    return face, np.clip(img, 0, 255).astype(np.uint8)


def skin_lab(rgb, face):
    m = lighting.skin_mask(rgb.shape[:2], face)
    lab = rgb_to_lab(rgb)[m]
    return np.median(lab, axis=0)


@pytest.mark.parametrize("skin", [(245, 215, 195), (190, 140, 115), (120, 80, 60), (75, 50, 38), (55, 38, 30)])
def test_well_exposed_faces_of_any_tone_are_left_alone(face_factory, policy, skin):
    # Correct exposure next to a light wall: no tone is pushed lighter or darker.
    face, rgb = portrait(face_factory, skin=skin)
    plan = lighting.plan(lighting.measure(rgb, face), policy)
    assert plan.exposure_ev == 0.0
    assert plan.contrast == 0.0


def test_underexposed_frame_is_brightened_within_cap(face_factory, policy):
    face, rgb = portrait(face_factory, gain=0.45)
    plan = lighting.plan(lighting.measure(rgb, face), policy)
    assert 0 < plan.exposure_ev <= policy["lighting"]["max_gain_ev"]


def test_bright_face_is_never_darkened_automatically(face_factory, policy):
    face, rgb = portrait(face_factory, skin=(250, 235, 225), wall=(250, 250, 250))
    plan = lighting.plan(lighting.measure(rgb, face), policy)
    assert plan.exposure_ev >= 0.0


def test_hazy_low_contrast_face_gets_bounded_contrast(face_factory, policy):
    face, rgb = portrait(face_factory, noise=1.0)
    haze = (rgb.astype(np.float32) * 0.3 + 150).astype(np.uint8)
    plan = lighting.plan(lighting.measure(haze, face), policy)
    assert 0 < plan.contrast <= policy["lighting"]["max_contrast_strength"]


def test_correction_preserves_skin_hue_and_chroma(face_factory, policy):
    face, rgb = portrait(face_factory, gain=0.5)
    plan = lighting.plan(lighting.measure(rgb, face), policy)
    out = lighting.apply(rgb, plan)
    before, after = skin_lab(rgb, face), skin_lab(out, face)
    hue_b = math.degrees(math.atan2(before[2], before[1]))
    hue_a = math.degrees(math.atan2(after[2], after[1]))
    assert abs(hue_a - hue_b) < 3.0
    assert after[0] > before[0]
    ok, _ = lighting.verify_skin(rgb, out, face, policy)
    assert ok


def test_identity_plan_returns_same_pixels(face_factory):
    face, rgb = portrait(face_factory)
    out = lighting.apply(rgb, lighting.LightingPlan())
    assert out is rgb


def test_weight_limits_correction_to_subject(face_factory):
    face, rgb = portrait(face_factory, gain=0.5)
    weight = np.zeros(rgb.shape[:2], np.float32)
    weight[:, :300] = 1.0
    out = lighting.apply(rgb, lighting.LightingPlan(exposure_ev=0.4), weight=weight)
    assert np.array_equal(out[:, 300:], rgb[:, 300:])
    assert out[:, :300].mean() > rgb[:, :300].mean()


def test_blown_out_face_warns(face_factory, policy):
    face, rgb = portrait(face_factory, skin=(252, 250, 248), noise=1.0, wall=(255, 255, 255))
    checks = lighting.lighting_checks(lighting.measure(rgb, face), policy)
    assert next(c for c in checks if c.id == "in.exposure").status == WARN


def test_side_shadow_warns_but_is_not_corrected(face_factory, policy):
    face, rgb = portrait(face_factory)
    rgb[:, : int(face.center_x)] = (rgb[:, : int(face.center_x)] * 0.45).astype(np.uint8)
    stats = lighting.measure(rgb, face)
    checks = lighting.lighting_checks(stats, policy)
    assert next(c for c in checks if c.id == "in.face_shadow").status == WARN
    plan = lighting.plan(stats, policy)
    assert plan.contrast <= policy["lighting"]["max_contrast_strength"]


def test_colour_cast_warns(face_factory, policy):
    face, rgb = portrait(face_factory, skin=(90, 140, 210))
    checks = lighting.lighting_checks(lighting.measure(rgb, face), policy)
    assert next(c for c in checks if c.id == "in.skin_tone").status == WARN


def test_normal_face_passes_all_lighting_checks(face_factory, policy):
    face, rgb = portrait(face_factory)
    checks = lighting.lighting_checks(lighting.measure(rgb, face), policy)
    bad = [c.id for c in checks if c.status != PASS and c.id != "in.sharpness"]
    assert not bad
