import math

import cv2
import numpy as np
import pytest

from app.pipeline.face_analysis import euler_from_matrix, eye_roll
from app.pipeline.tilt import Reference, _line_tilt, decide_tilt, scene_line_reference
from app.pipeline.transform import rotate, rotation_matrix, transform_points


# --- Rigid rotation -------------------------------------------------------------------------

def test_rotation_expands_canvas_and_keeps_all_pixels():
    m, (w, h) = rotation_matrix((50, 50), 30, (100, 60))
    corners = transform_points([[0, 0], [100, 0], [0, 60], [100, 60]], m)
    assert corners[:, 0].min() >= -1e-6 and corners[:, 1].min() >= -1e-6
    assert corners[:, 0].max() <= w + 1e-6 and corners[:, 1].max() <= h + 1e-6


@pytest.mark.parametrize("roll", [-9.0, -3.0, 2.5, 7.0])
def test_rotating_by_eye_roll_levels_the_eyes(roll):
    left = np.array([100.0, 200.0])
    right = left + 120 * np.array([math.cos(math.radians(roll)), math.sin(math.radians(roll))])
    assert eye_roll(left, right) == pytest.approx(roll)
    m, _ = rotation_matrix(tuple((left + right) / 2), roll, (400, 400))
    l2, r2 = transform_points(np.vstack([left, right]), m)
    assert eye_roll(l2, r2) == pytest.approx(0.0, abs=1e-6)
    # Rigid: distances are preserved (no warping of facial geometry).
    assert np.linalg.norm(r2 - l2) == pytest.approx(120.0)


def test_rotate_moves_image_and_matte_together_and_marks_valid_pixels():
    rgb = np.zeros((200, 300, 3), np.uint8)
    alpha = np.zeros((200, 300), np.uint8)
    cv2.circle(rgb, (150, 100), 20, (255, 255, 255), -1)
    cv2.circle(alpha, (150, 100), 20, 255, -1)
    r_rgb, r_alpha, valid, m = rotate(rgb, alpha, 10.0, (150, 100))
    assert r_rgb.shape[:2] == r_alpha.shape == valid.shape
    ys, xs = np.nonzero(r_alpha > 127)
    ys2, xs2 = np.nonzero(r_rgb[..., 0] > 127)
    assert abs(xs.mean() - xs2.mean()) < 1 and abs(ys.mean() - ys2.mean()) < 1
    assert valid[0, 0] == 0  # corners introduced by rotation are not source pixels
    assert valid[valid.shape[0] // 2, valid.shape[1] // 2] == 255


def test_euler_decomposition_roll_sign_matches_image_convention():
    # Canonical face rolled so that, on screen (y down), the right eye is lower.
    a = math.radians(-8.0)  # camera-space rotation about z (y up)
    r = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
    m = np.eye(4)
    m[:3, :3] = r
    yaw, pitch, roll = euler_from_matrix(m)
    assert roll == pytest.approx(8.0, abs=1e-6)
    assert yaw == pytest.approx(0.0, abs=1e-6) and pitch == pytest.approx(0.0, abs=1e-6)


# --- Camera tilt vs head tilt ------------------------------------------------------------

def test_line_tilt_convention_matches_eye_roll():
    kind, t = _line_tilt(0, 0, 100, 100 * math.tan(math.radians(4)))
    assert kind == "h" and t == pytest.approx(4.0)
    # Clockwise rotation leans a vertical line's top to the right: also positive.
    kind, t = _line_tilt(50, 100, 50 + 100 * math.tan(math.radians(4)), 0)
    assert kind == "v" and t == pytest.approx(4.0)


def _room(angle_deg: float) -> tuple[np.ndarray, np.ndarray]:
    """A plain wall with a door frame and a shelf, rotated as if the camera were rolled."""
    rgb = np.full((800, 600, 3), 200, np.uint8)
    cv2.rectangle(rgb, (60, 80), (160, 780), (90, 70, 50), 6)
    cv2.line(rgb, (380, 150), (590, 150), (60, 60, 60), 5)
    cv2.line(rgb, (500, 0), (500, 800), (120, 120, 120), 4)
    alpha = np.zeros((800, 600), np.uint8)
    cv2.ellipse(alpha, (300, 450), (110, 300), 0, 0, 360, 255, -1)
    m = cv2.getRotationMatrix2D((300, 400), -angle_deg, 1.0)
    rgb = cv2.warpAffine(rgb, m, (600, 800), borderMode=cv2.BORDER_REFLECT)
    alpha = cv2.warpAffine(alpha, m, (600, 800))
    return rgb, alpha


@pytest.mark.parametrize("angle", [-6.0, -2.0, 3.0, 5.0])
def test_scene_lines_measure_camera_roll(angle):
    rgb, alpha = _room(angle)
    ref = scene_line_reference(rgb, alpha)
    assert ref is not None
    assert ref.angle_deg == pytest.approx(angle, abs=0.6)


def test_scene_lines_absent_on_plain_wall():
    rgb = np.full((800, 600, 3), 210, np.uint8)
    alpha = np.zeros((800, 600), np.uint8)
    cv2.ellipse(alpha, (300, 450), (110, 300), 0, 0, 360, 255, -1)
    assert scene_line_reference(rgb, alpha) is None


def scene(angle, conf=0.9):
    return Reference("scene_lines", angle, conf)


def shoulders(angle, conf=0.95):
    return Reference("shoulders", angle, conf)


def test_level_eyes_need_no_rotation(policy):
    d = decide_tilt(0.2, 0.95, None, None, policy["tilt"])
    assert d.classification == "level" and not d.auto_apply and not d.suggest


def test_camera_tilt_confirmed_by_scene_lines_auto_rotates(policy):
    d = decide_tilt(4.3, 0.95, scene(4.0), None, policy["tilt"])
    assert d.classification == "camera_tilt"
    assert d.auto_apply
    assert d.angle_deg == pytest.approx(4.0)


def test_head_tilt_against_level_room_is_straightened(policy):
    d = decide_tilt(6.0, 0.95, scene(0.2), None, policy["tilt"])
    assert d.classification == "head_tilt"
    assert d.auto_apply and d.angle_deg == pytest.approx(6.0)  # levels the eyes, not the room


def test_head_tilt_against_level_shoulders_is_straightened(policy):
    d = decide_tilt(-5.0, 0.95, None, shoulders(0.3), policy["tilt"])
    assert d.classification == "head_tilt" and d.auto_apply
    assert d.angle_deg == pytest.approx(-5.0)


def test_shoulder_agreement_is_straightened(policy):
    d = decide_tilt(3.0, 0.95, None, shoulders(2.4), policy["tilt"])
    assert d.classification == "camera_tilt"
    assert d.auto_apply and not d.suggest
    assert d.angle_deg == pytest.approx(2.7)


def test_no_reference_is_ambiguous_but_straightened(policy):
    d = decide_tilt(3.0, 0.95, None, None, policy["tilt"])
    assert d.classification == "ambiguous"
    assert d.auto_apply and d.angle_deg == pytest.approx(3.0)
    assert d.confidence < 0.5


def test_tilt_within_landmark_noise_is_not_straightened(policy):
    d = decide_tilt(1.0, 0.95, None, shoulders(0.2), policy["tilt"])
    assert d.classification == "head_tilt" and not d.auto_apply and d.angle_deg == 0.0
    d = decide_tilt(-1.2, 0.95, None, None, policy["tilt"])
    assert d.classification == "ambiguous" and not d.auto_apply and d.suggest


def test_head_tilt_is_only_reported_when_straightening_is_off(policy):
    tp = {**policy["tilt"], "straighten_head_tilt": False}
    d = decide_tilt(6.0, 0.95, scene(0.2), None, tp)
    assert d.classification == "head_tilt" and not d.auto_apply and d.angle_deg == 0.0
    d = decide_tilt(3.0, 0.95, None, shoulders(2.4), tp)
    assert not d.auto_apply and d.suggest
    d = decide_tilt(3.0, 0.95, None, None, tp)
    assert d.classification == "ambiguous" and not d.auto_apply and d.suggest


def test_low_face_confidence_blocks_auto_rotation(policy):
    d = decide_tilt(4.0, 0.72, scene(4.0), None, policy["tilt"])
    assert d.classification == "camera_tilt" and not d.auto_apply and d.suggest
    d = decide_tilt(6.0, 0.72, scene(0.2), None, policy["tilt"])
    assert d.classification == "head_tilt" and not d.auto_apply and d.suggest


@pytest.mark.parametrize("ref", [scene(14.0), scene(0.2), None])
def test_large_tilt_is_never_auto_rotated(policy, ref):
    d = decide_tilt(14.0, 0.95, ref, None, policy["tilt"])
    assert not d.auto_apply and d.suggest
    assert d.angle_deg == pytest.approx(14.0)


def test_disagreeing_references_are_ambiguous_and_straightened(policy):
    d = decide_tilt(6.0, 0.95, scene(2.5), shoulders(-2.0), policy["tilt"])
    assert d.classification == "ambiguous" and d.auto_apply
    assert d.angle_deg == pytest.approx(6.0)
