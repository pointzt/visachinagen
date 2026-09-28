import io

import cv2
import numpy as np
import pytest
from PIL import Image

from app.pipeline.geometry import CropPlan
from app.pipeline.render import crop_scale, encode_jpeg, render
from app.pipeline.spec import constraints_for

WHITE = (255, 255, 255)


def textured(h=560, w=420, seed=1):
    rng = np.random.default_rng(seed)
    img = rng.integers(0, 255, (h // 8, w // 8, 3), dtype=np.uint8)
    return cv2.resize(img, (w, h), interpolation=cv2.INTER_LINEAR)


def test_jpeg_metadata_and_size_window(spec):
    c = constraints_for(spec, "digital")
    data, quality, notes = encode_jpeg(textured(), c.dpi, c.min_kb, c.max_kb)
    img = Image.open(io.BytesIO(data))
    assert img.format == "JPEG" and img.mode == "RGB"
    assert img.size == (420, 560)
    assert round(img.info["dpi"][0]) == 300
    assert not img.info.get("progressive")
    assert len(img.getexif()) == 0
    assert c.min_kb * 1024 <= len(data) <= c.max_kb * 1024
    assert not notes


def test_encoder_raises_quality_for_tiny_files(spec):
    c = constraints_for(spec, "digital")
    flat = np.full((560, 420, 3), 255, np.uint8)
    data, quality, notes = encode_jpeg(flat, c.dpi, c.min_kb, c.max_kb)
    assert quality == 100
    assert notes  # a flat white image cannot reach 40 KB; this is reported, not hidden


def test_encoder_reduces_quality_for_large_files():
    noisy = np.random.default_rng(0).integers(0, 255, (560, 420, 3), dtype=np.uint8)
    data, quality, _ = encode_jpeg(noisy, 300, None, 120)
    assert quality < 95


def test_crop_scale_places_source_and_marks_coverage(spec):
    c = constraints_for(spec, "digital")
    rgb = np.full((300, 300, 3), 100, np.uint8)
    alpha = np.full((300, 300), 255, np.uint8)
    valid = np.full((300, 300), 255, np.uint8)
    plan = CropPlan(scale=1.0, tx=60.0, ty=-10.0, feasible=True)
    out, a, cov = crop_scale(rgb, alpha, valid, plan, c)
    assert out.shape == (560, 420, 3)
    assert cov[0, 60] and not cov[0, 59]
    assert cov[289, 200] and not cov[290, 200]
    assert (a[~cov] == 0).all()


def test_render_composites_exact_background_colour(spec):
    c = constraints_for(spec, "digital")
    rgb = np.full((600, 450, 3), (40, 120, 200), np.uint8)
    alpha = np.zeros((600, 450), np.uint8)
    cv2.circle(alpha, (225, 300), 120, 255, -1)
    rgb[alpha > 0] = (160, 110, 90)
    valid = np.full((600, 450), 255, np.uint8)
    plan = CropPlan(scale=1.0, tx=-15.0, ty=-20.0, feasible=True)
    out = render(rgb, alpha, valid, plan, c, WHITE, None, replace_background=True, edge_refine=False)
    assert tuple(out.rgb[5, 5]) == WHITE
    assert tuple(out.rgb[280, 210]) == (160, 110, 90)


def test_render_keeps_original_background_when_asked(spec):
    c = constraints_for(spec, "digital")
    rgb = np.full((600, 450, 3), (240, 240, 240), np.uint8)
    alpha = np.zeros((600, 450), np.uint8)
    valid = np.full((600, 450), 255, np.uint8)
    plan = CropPlan(scale=1.0, tx=-15.0, ty=-20.0, feasible=True)
    out = render(rgb, alpha, valid, plan, c, WHITE, None, replace_background=False)
    assert tuple(out.rgb[5, 5]) == (240, 240, 240)


@pytest.mark.models
def test_validator_reports_file_rules_on_exported_bytes(spec, policy):
    from app.pipeline.output_validator import validate_output
    c = constraints_for(spec, "digital")
    data, _, _ = encode_jpeg(textured(), c.dpi, c.min_kb, c.max_kb)
    checks, measured = validate_output(data, c, spec, policy, WHITE, None, None)
    ids = {x.id: x for x in checks}
    assert ids["out.dimensions"].status == "pass"
    assert ids["out.file_size"].status == "pass"
    assert ids["out.format"].status == "pass"
    assert ids["out.face"].status == "fail"  # no face in random texture: geometry unverifiable
    assert measured["dpi"] == 300


@pytest.mark.models
def test_validator_rejects_wrong_size_and_oversized_file(spec, policy):
    from app.pipeline.output_validator import validate_output
    c = constraints_for(spec, "digital")
    noisy = np.random.default_rng(0).integers(0, 255, (600, 450, 3), dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(noisy).save(buf, format="JPEG", quality=100)
    checks, _ = validate_output(buf.getvalue(), c, spec, policy, WHITE, None, None)
    ids = {x.id: x for x in checks}
    assert ids["out.dimensions"].status == "fail"
    assert ids["out.file_size"].status == "fail"
