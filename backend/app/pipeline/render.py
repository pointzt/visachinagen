"""Render the final photo: crop/scale, matte refinement, lighting, background composite, encode."""

import io
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

from app.pipeline import lighting as lighting_mod
from app.pipeline.geometry import CropPlan
from app.pipeline.spec import Constraints


@dataclass
class Rendered:
    rgb: np.ndarray
    alpha: np.ndarray  # float32 0..1
    coverage: np.ndarray  # bool: pixel came from the source photo


def _place(src: np.ndarray, u0: int, v0: int, width: int, height: int, fill) -> np.ndarray:
    shape = (height, width) + src.shape[2:]
    canvas = np.empty(shape, dtype=src.dtype)
    canvas[...] = fill
    sh, sw = src.shape[:2]
    x0, y0 = max(0, u0), max(0, v0)
    x1, y1 = min(sw, u0 + width), min(sh, v0 + height)
    if x1 > x0 and y1 > y0:
        canvas[y0 - v0:y1 - v0, x0 - u0:x1 - u0] = src[y0:y1, x0:x1]
    return canvas


def crop_scale(rgb: np.ndarray, alpha: np.ndarray, valid: np.ndarray, plan: CropPlan, c: Constraints):
    h, w = rgb.shape[:2]
    s = plan.scale
    size = (max(1, int(round(w * s))), max(1, int(round(h * s))))
    interp = cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC
    rgb_s = cv2.resize(rgb, size, interpolation=interp)
    alpha_s = cv2.resize(alpha, size, interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR)
    valid_s = cv2.resize(valid, size, interpolation=cv2.INTER_NEAREST)
    u0, v0 = int(-plan.tx), int(-plan.ty)
    return (
        _place(rgb_s, u0, v0, c.width, c.height, 0),
        _place(alpha_s, u0, v0, c.width, c.height, 0),
        _place(valid_s, u0, v0, c.width, c.height, 0) > 0,
    )


def refine_foreground(rgb: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    """Estimate true foreground colours in semi-transparent edge pixels (removes colour spill
    from the old background in hair). Only pixels with 0 < alpha < 1 change."""
    from pymatting import estimate_foreground_ml

    img = rgb.astype(np.float64) / 255.0
    fg = estimate_foreground_ml(img, alpha.astype(np.float64))
    fg = np.clip(fg * 255.0, 0, 255)
    solid = alpha >= 0.995
    fg[solid] = rgb[solid]
    return fg.astype(np.uint8)


def render(rgb: np.ndarray, alpha: np.ndarray, valid: np.ndarray, plan: CropPlan, c: Constraints,
           bg_rgb: tuple[int, int, int], light: lighting_mod.LightingPlan | None,
           replace_background: bool = True, edge_refine: bool = True) -> Rendered:
    crop_rgb, crop_a, coverage = crop_scale(rgb, alpha, valid, plan, c)
    a = crop_a.astype(np.float32) / 255.0
    a[~coverage] = 0.0
    bg = np.empty_like(crop_rgb)
    bg[...] = bg_rgb

    if replace_background:
        fg = refine_foreground(crop_rgb, a) if edge_refine else crop_rgb
        if light is not None:
            fg = lighting_mod.apply(fg, light)
        out = fg.astype(np.float32) * a[..., None] + bg.astype(np.float32) * (1 - a[..., None])
    else:
        base = np.where(coverage[..., None], crop_rgb, bg)
        out = lighting_mod.apply(base, light, weight=a) if light is not None else base
    return Rendered(np.clip(np.round(out), 0, 255).astype(np.uint8), a, coverage)


def encode_jpeg(rgb: np.ndarray, dpi: int, min_kb: float | None, max_kb: float | None) -> tuple[bytes, int, list[str]]:
    """Baseline JPEG, 4:4:4, sRGB, no EXIF, DPI tag set, sized into [min_kb, max_kb] when possible."""
    img = Image.fromarray(rgb, mode="RGB")
    notes = []

    def enc(q: int) -> bytes:
        buf = io.BytesIO()
        try:
            img.save(buf, format="JPEG", quality=q, optimize=True, dpi=(dpi, dpi), subsampling=0)
        except OSError:
            # libjpeg's Huffman optimisation can overflow Pillow's buffer on very detailed images.
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=q, optimize=False, dpi=(dpi, dpi), subsampling=0)
        return buf.getvalue()

    for q in (95, 92, 90, 87, 85, 82, 80, 75, 70, 65, 60):
        data = enc(q)
        if max_kb is None or len(data) <= max_kb * 1024:
            break
    else:
        notes.append("Could not reach the maximum file size even at quality 60.")
    if min_kb is not None and len(data) < min_kb * 1024:
        data, q = enc(100), 100
        if len(data) < min_kb * 1024:
            notes.append("File is below the minimum size even at maximum quality.")
    return data, q, notes
