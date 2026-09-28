import numpy as np
import pytest

from app.pipeline.geometry import CropAdjust, solve
from app.pipeline.head_measure import HeadMeasure, measure_head
from app.pipeline.spec import constraints_for


def head(crown=100.0, chin=800.0, eye=450.0, cx=500.0, fw=390.0, inter=180.0, anat=None, source="silhouette"):
    return HeadMeasure(crown_y=crown, chin_y=chin, eye_y=eye, center_x=cx, face_width=fw, inter_eye=inter,
                       crown_source=source, silhouette_crown_y=crown,
                       anatomical_crown_y=anat if anat is not None else crown + 0.08 * (chin - crown),
                       crown_clipped=False)


def within(value, rng):
    return rng.contains(value)


@pytest.mark.parametrize("profile", ["digital", "paper"])
def test_typical_head_satisfies_all_rules(spec, profile):
    c = constraints_for(spec, profile)
    plan = solve(head(), c)
    p = plan.predicted
    assert plan.feasible
    assert within(p["crown_to_top"], c.crown_to_top)
    if c.eye_line_to_bottom:
        assert within(p["eye_line_to_bottom"], c.eye_line_to_bottom)
    if c.face_width:
        assert within(p["face_width"], c.face_width)
    if c.head_height:
        assert within(p["head_height"], c.head_height)
    if c.chin_to_bottom:
        assert within(p["chin_to_bottom"], c.chin_to_bottom)
    assert abs(p["center_offset"]) <= 1.0


def test_digital_targets_mid_face_width(spec):
    c = constraints_for(spec, "digital")
    plan = solve(head(), c)
    assert plan.predicted["face_width"] == pytest.approx(c.face_width.target, rel=0.02)


def test_plan_keeps_safety_margin_inside_ranges(spec):
    c = constraints_for(spec, "digital")
    # Tall hair pushes the crown up; the plan must not sit exactly on the limit.
    plan = solve(head(crown=0.0, chin=800.0, eye=470.0), c)
    if plan.feasible:
        assert plan.predicted["crown_to_top"] >= c.crown_to_top.min + 0.01 * c.height
        assert plan.predicted["eye_line_to_bottom"] > c.eye_line_to_bottom.min + 0.009 * c.height


def test_translation_is_integral(spec):
    plan = solve(head(cx=333.3, eye=451.7), constraints_for(spec, "digital"))
    assert plan.tx == int(plan.tx) and plan.ty == int(plan.ty)


def test_infeasible_proportions_are_reported(spec):
    c = constraints_for(spec, "digital")
    # Eyes very low relative to the crown: cannot keep crown <= 70 ref px and eyes > 256 ref px from bottom.
    bad = head(crown=100.0, chin=800.0, eye=760.0, fw=300.0)
    plan = solve(bad, c)
    assert not plan.feasible
    assert plan.notes


def test_voluminous_hair_is_trimmed_when_needed(spec, policy):
    c = constraints_for(spec, "digital")
    # A tall bun: silhouette crown far above the anatomical crown.
    h = head(crown=0.0, chin=800.0, eye=500.0, fw=380.0, anat=180.0)
    plan = solve(h, c, hair_allowance=policy["crown"]["hair_allowance"])
    assert plan.feasible
    assert plan.head.crown_source == "hair_trimmed"
    assert any("trimmed" in n for n in plan.notes)


def test_manual_zoom_keeps_eyes_anchored(spec):
    c = constraints_for(spec, "digital")
    h = head()
    base = solve(h, c)
    zoomed = solve(h, c, CropAdjust(scale=1.1))
    assert zoomed.scale == pytest.approx(base.scale * 1.1)
    eye_base = c.height - base.predicted["eye_line_to_bottom"]
    eye_zoom = c.height - zoomed.predicted["eye_line_to_bottom"]
    assert eye_zoom == pytest.approx(eye_base, abs=1.0)
    assert abs(zoomed.predicted["center_offset"]) <= 1.0


def test_manual_offset_moves_crop(spec):
    c = constraints_for(spec, "digital")
    h = head()
    base = solve(h, c)
    moved = solve(h, c, CropAdjust(offset_y=0.05))
    assert moved.ty - base.ty == pytest.approx(0.05 * c.height, abs=1.0)


def test_source_rect_round_trip(spec):
    c = constraints_for(spec, "digital")
    plan = solve(head(), c)
    x0, y0, w, h = plan.source_rect(c)
    assert w * plan.scale == pytest.approx(c.width)
    assert (x0 * plan.scale + plan.tx) == pytest.approx(0, abs=1e-6)


# --- Head measurement on synthetic masks --------------------------------------------------

def test_crown_from_silhouette(face_factory, mask_factory, policy):
    face = face_factory(cx=300, eye_y=400, face_width=200, image_size=(600, 900))
    mask = mask_factory(face, (900, 600), hair_ratio=1.40)
    hm = measure_head(face, mask, policy)
    expected = face.chin[1] - (face.chin[1] - face.forehead_top[1]) * 1.40
    assert hm.crown_source == "silhouette"
    assert hm.crown_y == pytest.approx(expected, abs=4)
    assert hm.head_height == pytest.approx(face.chin[1] - expected, abs=4)


def test_voluminous_hair_uses_anatomical_crown(face_factory, mask_factory, policy):
    face = face_factory(cx=300, eye_y=450, face_width=200, image_size=(600, 900))
    mask = mask_factory(face, (900, 600), hair_ratio=1.75)
    hm = measure_head(face, mask, policy)
    assert hm.crown_source == "anatomical_voluminous_hair"
    assert hm.crown_y > hm.silhouette_crown_y


def test_crown_cut_off_by_frame_is_flagged(face_factory, mask_factory, policy):
    face = face_factory(cx=300, eye_y=150, face_width=200, image_size=(600, 900))
    mask = mask_factory(face, (900, 600), hair_ratio=1.40)
    hm = measure_head(face, mask, policy)
    assert hm.crown_clipped
    assert hm.crown_source == "anatomical_clipped"


def test_measurements_scale_linearly(face_factory, mask_factory, policy):
    small = face_factory(cx=150, eye_y=200, face_width=100, image_size=(300, 450))
    large = face_factory(cx=300, eye_y=400, face_width=200, image_size=(600, 900))
    a = measure_head(small, mask_factory(small, (450, 300)), policy)
    b = measure_head(large, mask_factory(large, (900, 600)), policy)
    assert b.head_height / a.head_height == pytest.approx(2.0, rel=0.03)
    assert b.inter_eye / a.inter_eye == pytest.approx(2.0, rel=1e-6)
    assert np.isclose(b.face_width, 2 * a.face_width)
