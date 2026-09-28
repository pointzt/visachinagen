import cv2
import numpy as np

from app.pipeline.background_qa import (check_kept_background, check_matte, check_output_background,
                                        enclosed_holes)
from app.pipeline.checks import FAIL, PASS, WARN
from app.pipeline.head_measure import measure_head

WHITE = (255, 255, 255)


def scene(face_factory, mask_factory, garment=(30, 40, 90), bg=(120, 160, 200)):
    face = face_factory(cx=300, eye_y=380, face_width=200, image_size=(600, 900))
    fg = mask_factory(face, (900, 600))
    rgb = np.empty((900, 600, 3), np.uint8)
    rgb[...] = bg
    rgb[fg] = (200, 150, 120)
    body = fg.copy()
    body[: int(face.chin[1] + 20)] = False
    rgb[body] = garment
    alpha = (fg * 255).astype(np.uint8)
    return face, rgb, alpha


def by_id(checks, cid):
    return next(c for c in checks if c.id == cid)


def test_clean_matte_passes(face_factory, mask_factory, policy):
    face, rgb, alpha = scene(face_factory, mask_factory)
    head = measure_head(face, alpha > 127, policy)
    checks, _ = check_matte(rgb, alpha, face, head, WHITE, policy)
    assert all(c.status == PASS for c in checks), [(c.id, c.status) for c in checks]


def test_hole_in_face_fails(face_factory, mask_factory, policy):
    face, rgb, alpha = scene(face_factory, mask_factory)
    cv2.circle(alpha, (int(face.center_x + 40), int(face.eye_mid[1] + 60)), 18, 0, -1)
    head = measure_head(face, alpha > 127, policy)
    checks, _ = check_matte(rgb, alpha, face, head, WHITE, policy)
    assert by_id(checks, "bg.face_coverage").status == FAIL
    assert by_id(checks, "bg.head_holes").status == FAIL
    assert by_id(checks, "bg.head_holes").remedy == "retake"


def test_gaps_in_hair_only_warn(face_factory, mask_factory, policy):
    face, rgb, alpha = scene(face_factory, mask_factory)
    head = measure_head(face, alpha > 127, policy)
    for dx in (-60, -20, 20, 60):
        cv2.circle(alpha, (int(face.center_x + dx), int(head.crown_y + 26)), 14, 0, -1)
    checks, _ = check_matte(rgb, alpha, face, head, WHITE, policy)
    assert by_id(checks, "bg.face_coverage").status == PASS
    assert by_id(checks, "bg.head_holes").status == WARN


def test_white_garment_on_white_background_warns(face_factory, mask_factory, policy):
    face, rgb, alpha = scene(face_factory, mask_factory, garment=(250, 250, 248))
    head = measure_head(face, alpha > 127, policy)
    checks, _ = check_matte(rgb, alpha, face, head, WHITE, policy)
    assert by_id(checks, "bg.garment_contrast").status == WARN


def test_shadow_kept_in_cutout_warns(face_factory, mask_factory, policy):
    face, rgb, alpha = scene(face_factory, mask_factory, bg=(200, 200, 200))
    fg = alpha > 127
    # Segmentation swallowed a dark band of wall (the person's shadow) along the outline.
    grown = cv2.dilate(fg.astype(np.uint8), np.ones((31, 31), np.uint8)).astype(bool)
    shadow = grown & ~fg
    shadow[: int(face.chin[1])] = False
    rgb[shadow] = (150, 150, 150)
    alpha[shadow] = 255
    head = measure_head(face, alpha > 127, policy)
    checks, _ = check_matte(rgb, alpha, face, head, WHITE, policy)
    assert by_id(checks, "bg.shadow_edges").status == WARN


def test_enclosed_holes_ignores_border_connected_background():
    fg = np.zeros((100, 100), bool)
    fg[20:80, 20:80] = True
    fg[40:50, 40:50] = False
    fg[60:80, 0:20] = True
    holes = enclosed_holes(fg)
    assert holes.sum() == 100


def test_kept_background_must_be_white(face_factory, mask_factory, spec):
    _, rgb, alpha = scene(face_factory, mask_factory, bg=(90, 140, 210))
    assert check_kept_background(rgb, alpha, spec["background"]).status == FAIL
    _, rgb, alpha = scene(face_factory, mask_factory, bg=(250, 250, 250))
    assert check_kept_background(rgb, alpha, spec["background"]).status == PASS


def output_image(ring_color=None):
    rgb = np.full((560, 420, 3), 255, np.uint8)
    a = np.zeros((560, 420), np.float32)
    cv2.ellipse(a, (210, 260), (110, 150), 0, 0, 360, 1.0, -1)
    cv2.rectangle(a, (40, 420), (380, 560), 1.0, -1)
    rgb[a > 0.5] = (180, 130, 110)
    if ring_color is not None:
        ring = cv2.dilate((a > 0.5).astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool) & (a < 0.5)
        rgb[ring] = ring_color
    return rgb, a


def test_output_background_uniform_white_passes(spec, policy):
    rgb, a = output_image()
    checks = check_output_background(rgb, a > 0.5, WHITE, spec["background"], a, policy)
    assert by_id(checks, "out.background_color").status == PASS
    assert by_id(checks, "out.no_border").status == PASS
    assert by_id(checks, "out.halo").status == PASS


def test_halo_is_detected(spec, policy):
    rgb, a = output_image(ring_color=(150, 170, 200))
    checks = check_output_background(rgb, a > 0.5, WHITE, spec["background"], a, policy)
    assert by_id(checks, "out.halo").status == WARN


def test_border_is_detected(spec, policy):
    rgb, a = output_image()
    rgb[:, :2] = (40, 40, 40)
    fg = a > 0.5
    checks = check_output_background(rgb, fg, WHITE, spec["background"], a, policy)
    assert by_id(checks, "out.no_border").status == FAIL


def test_grey_background_fails(spec, policy):
    rgb, a = output_image()
    rgb[a < 0.5] = (215, 215, 215)
    checks = check_output_background(rgb, a > 0.5, WHITE, spec["background"], a, policy)
    assert by_id(checks, "out.background_color").status == FAIL
