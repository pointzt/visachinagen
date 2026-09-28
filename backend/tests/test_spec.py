import pytest

from app.pipeline.spec import constraints_for, load_spec


def test_spec_is_versioned_and_sourced(spec):
    assert spec["version"] == "1.0.0"
    assert "MFA 2016" in spec["source"]["edition"]
    assert spec["background"]["color"] == "#FFFFFF"


def test_every_threshold_has_a_status(spec):
    def walk(node, path=""):
        if isinstance(node, dict):
            if {"min", "max", "min_exclusive", "value"} & node.keys():
                assert node.get("status") in ("verified", "provisional"), path
            for k, v in node.items():
                if k not in ("policy", "status_legend"):
                    walk(v, f"{path}.{k}")
    walk(spec["profiles"])
    walk(spec["background"])
    assert spec["policy"]["status"] == "provisional"


def test_digital_constraints_scale_from_reference_frame(spec):
    c = constraints_for(spec, "digital")
    assert (c.width, c.height) == (420, 560)
    k = 560 / 472
    assert c.crown_to_top.min == pytest.approx(10 * k)
    assert c.crown_to_top.max == pytest.approx(70 * k)
    assert c.face_width.min == pytest.approx(191 * k)
    assert c.face_width.max == pytest.approx(219 * k)
    assert c.eye_line_to_bottom.exclusive_min and c.eye_line_to_bottom.min == pytest.approx(256 * k)
    assert c.inter_eye_distance.min == pytest.approx(60 * k)
    assert (c.min_kb, c.max_kb) == (40, 120)
    assert c.allowed_size == {"min_width_px": 354, "min_height_px": 472, "max_width_px": 420, "max_height_px": 560}
    assert c.scale_metric == "face_width"


def test_digital_output_is_within_allowed_size(spec):
    c = constraints_for(spec, "digital")
    a = c.allowed_size
    assert a["min_width_px"] <= c.width <= a["max_width_px"]
    assert a["min_height_px"] <= c.height <= a["max_height_px"]
    assert c.width / c.height == pytest.approx(354 / 472)


def test_paper_constraints_in_mm(spec):
    c = constraints_for(spec, "paper")
    assert (c.width, c.height) == (390, 567)  # 33 x 48 mm at 300 dpi
    px_per_mm = 300 / 25.4
    assert c.head_height.min == pytest.approx(28 * px_per_mm)
    assert c.head_height.max == pytest.approx(33 * px_per_mm)
    assert c.crown_to_top.min == pytest.approx(3 * px_per_mm)
    assert c.chin_to_bottom.min == pytest.approx(7 * px_per_mm)
    assert c.scale_metric == "head_height"


def test_unknown_profile_and_spec():
    with pytest.raises(ValueError):
        constraints_for(load_spec("CHINA_VISA"), "billboard")
    with pytest.raises(ValueError):
        load_spec("NOWHERE_VISA")
