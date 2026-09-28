"""Conservative exposure and contrast correction.

Only global, chroma-preserving operations are used: a linear-light exposure gain and a gentle
contrast stretch applied to luminance, with RGB scaled by the same ratio so hue and saturation
are unchanged. No local tone mapping, smoothing, relighting or reshaping.

Skin tone is never used as an exposure target. A face is only treated as underexposed when
its highlights are dark *and* the whole scene lacks highlights (nothing in the frame is bright),
which is what an underexposed camera frame looks like. A dark-skinned person photographed
correctly next to a light wall or shirt is left alone. Exposure is never reduced automatically:
clipped highlights cannot be recovered, so they are reported instead.
"""

import math
from dataclasses import dataclass, field

import cv2
import numpy as np

from app.pipeline.background_qa import face_polygon_mask
from app.pipeline.checks import PASS, WARN, Check
from app.pipeline.color import linear_to_srgb, rgb_to_lab, srgb_to_linear
from app.pipeline.face_analysis import FaceAnalysis

FOREHEAD_PATCH = 151
# Mid-cheek points below the eyes; chosen over 50/280 (next to the smile fold) because they gave
# the most stable left/right comparison on the calibration set (median 3.8 L* vs 10.4).
CHEEK_PATCHES = (101, 330)


@dataclass
class LightingStats:
    p2: float
    p50: float
    p98: float
    scene_p99: float
    face_range: float
    face_black: float
    clipped: float
    crushed: float
    asymmetry: float
    sharpness: float
    skin_hue_deg: float
    skin_chroma: float

    def as_dict(self) -> dict:
        return {k: round(v, 3) for k, v in self.__dict__.items()}


@dataclass
class LightingPlan:
    exposure_ev: float = 0.0
    contrast: float = 0.0
    pivot: float = 0.5
    reasons: list[str] = field(default_factory=list)

    @property
    def is_identity(self) -> bool:
        return abs(self.exposure_ev) < 1e-3 and abs(self.contrast) < 1e-3

    def as_dict(self) -> dict:
        return {"exposure_ev": round(self.exposure_ev, 3), "contrast": round(self.contrast, 3), "reasons": self.reasons}


def skin_patches(shape: tuple[int, int], face: FaceAnalysis) -> dict[str, np.ndarray]:
    """Small discs on the forehead and both upper cheeks: skin in almost every face, and away
    from eyes, brows, teeth and facial hair that would distort exposure statistics."""
    r = max(2, int(0.07 * face.face_width))
    out = {}
    for name, idx in (("forehead", FOREHEAD_PATCH), ("cheek_a", CHEEK_PATCHES[0]), ("cheek_b", CHEEK_PATCHES[1])):
        m = np.zeros(shape, np.uint8)
        x, y = face.landmarks[idx]
        cv2.circle(m, (int(round(x)), int(round(y))), r, 1, -1)
        out[name] = m.astype(bool)
    return out


def skin_mask(shape: tuple[int, int], face: FaceAnalysis) -> np.ndarray:
    p = skin_patches(shape, face)
    return p["forehead"] | p["cheek_a"] | p["cheek_b"]


def measure(rgb: np.ndarray, face: FaceAnalysis) -> LightingStats:
    patches = skin_patches(rgb.shape[:2], face)
    mask = patches["forehead"] | patches["cheek_a"] | patches["cheek_b"]
    lab = rgb_to_lab(rgb)
    L = lab[..., 0][mask]
    px = rgb[mask]
    left, right = lab[..., 0][patches["cheek_a"]], lab[..., 0][patches["cheek_b"]]
    asym = abs(float(np.median(left)) - float(np.median(right))) if left.size > 10 and right.size > 10 else 0.0

    x0, y0 = np.floor(face.oval.min(axis=0)).astype(int)
    x1, y1 = np.ceil(face.oval.max(axis=0)).astype(int)
    crop = cv2.cvtColor(rgb[max(0, y0):y1, max(0, x0):x1], cv2.COLOR_RGB2GRAY)
    sharp = 0.0
    if crop.size:
        scale = 200.0 / max(1, crop.shape[1])
        crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
        sharp = float(cv2.Laplacian(crop, cv2.CV_64F).var())

    a_med, b_med = float(np.median(lab[..., 1][mask])), float(np.median(lab[..., 2][mask]))
    oval = face_polygon_mask(rgb.shape[:2], face, shrink=0.04)
    face_L = lab[..., 0][oval]
    return LightingStats(
        p2=float(np.percentile(L, 2)), p50=float(np.median(L)), p98=float(np.percentile(L, 98)),
        scene_p99=float(np.percentile(lab[..., 0], 99)),
        face_range=float(np.percentile(face_L, 98) - np.percentile(face_L, 2)),
        face_black=float(np.percentile(face_L, 2)),
        clipped=float((px.min(axis=1) >= 245).mean()), crushed=float((L < 8).mean()),
        asymmetry=asym, sharpness=sharp,
        skin_hue_deg=math.degrees(math.atan2(b_med, a_med)), skin_chroma=math.hypot(a_med, b_med),
    )


def _lightness_to_luminance(L: float) -> float:
    fy = (L + 16) / 116
    return fy ** 3 if fy ** 3 > 0.008856 else (L / 903.3)


def plan(stats: LightingStats, policy: dict) -> LightingPlan:
    p = policy["lighting"]
    result = LightingPlan()
    if stats.p98 < p["under_p98_lightness"] and stats.scene_p99 < p["under_scene_p99_lightness"]:
        # Lift until the brightest part of the scene reaches a normal highlight level, capped.
        y_now = max(1e-4, _lightness_to_luminance(stats.scene_p99))
        ev = math.log2(_lightness_to_luminance(p["target_scene_p99_lightness"]) / y_now)
        result.exposure_ev = float(np.clip(ev, 0.0, p["max_gain_ev"]))
        if result.exposure_ev > 0.01:
            result.reasons.append(
                f"Whole photo is dark (brightest areas L* {stats.scene_p99:.0f}); brightened by {result.exposure_ev:+.2f} EV.")
        else:
            result.exposure_ev = 0.0
    # Haze lifts the blacks: pupils and brows are no longer dark. A small L* range alone is not
    # enough, because very dark skin with dark eyes naturally has a small range.
    if stats.face_range < p["low_range_lightness"] and stats.face_black > p["haze_black_lightness"]:
        result.contrast = min(p["max_contrast_strength"],
                              (p["low_range_lightness"] - stats.face_range) / p["low_range_lightness"])
        result.pivot = stats.p50 / 100.0
        result.reasons.append(f"Flat, hazy face (range {stats.face_range:.0f} L*); contrast +{result.contrast * 100:.0f}%.")
    return result


def apply(rgb: np.ndarray, lp: LightingPlan, weight: np.ndarray | None = None) -> np.ndarray:
    """Apply ``lp`` to a uint8 RGB image. ``weight`` (0..1) restricts it to the subject."""
    if lp.is_identity:
        return rgb
    x = srgb_to_linear(rgb.astype(np.float32) / 255.0)
    y = 0.2126 * x[..., 0] + 0.7152 * x[..., 1] + 0.0722 * x[..., 2]
    y_new = y * (2.0 ** lp.exposure_ev)
    if lp.contrast:
        enc = linear_to_srgb(y_new)
        enc = np.clip(lp.pivot + (enc - lp.pivot) * (1.0 + lp.contrast), 0.0, 1.0)
        y_new = srgb_to_linear(enc)
    ratio = np.where(y > 1e-5, y_new / np.maximum(y, 1e-5), 1.0)
    out = x * ratio[..., None]
    # Keep hue when a channel would clip: scale the pixel down instead of clipping one channel.
    peak = out.max(axis=-1, keepdims=True)
    out = out / np.maximum(peak, 1.0)
    out = linear_to_srgb(out) * 255.0
    if weight is not None:
        wgt = weight[..., None]
        out = out * wgt + rgb.astype(np.float32) * (1 - wgt)
    return np.clip(np.round(out), 0, 255).astype(np.uint8)


def verify_skin(before: np.ndarray, after: np.ndarray, face: FaceAnalysis, policy: dict) -> tuple[bool, str]:
    p = policy["lighting"]
    mask = skin_mask(before.shape[:2], face)
    lb, la = rgb_to_lab(before)[mask], rgb_to_lab(after)[mask]
    hb = math.degrees(math.atan2(np.median(lb[:, 2]), np.median(lb[:, 1])))
    ha = math.degrees(math.atan2(np.median(la[:, 2]), np.median(la[:, 1])))
    # Saturation (C*/L*) rather than raw chroma: a pure exposure change scales C* with L*.
    sb = math.hypot(np.median(lb[:, 1]), np.median(lb[:, 2])) / max(1.0, float(np.median(lb[:, 0])))
    sa = math.hypot(np.median(la[:, 1]), np.median(la[:, 2])) / max(1.0, float(np.median(la[:, 0])))
    hue_shift = abs((ha - hb + 180) % 360 - 180)
    sat_change = abs(sa / max(sb, 1e-3) - 1.0)
    if hue_shift > p["max_hue_shift_deg"] or sat_change > p["max_saturation_ratio_change"]:
        return False, f"Correction reverted: skin hue would shift {hue_shift:.1f}° / saturation {sat_change * 100:.0f}%."
    return True, f"Skin tone preserved (hue shift {hue_shift:.1f}°, saturation change {sat_change * 100:.0f}%)."


def lighting_checks(stats: LightingStats, policy: dict, stage: str = "input") -> list[Check]:
    p = policy["lighting"]
    checks = []
    over = stats.clipped > p["clip_warn_fraction"]
    under = stats.crushed > p["crushed_warn_fraction"]
    checks.append(Check(
        f"{stage[:2]}.exposure", "lighting", "Face is not over- or under-exposed",
        WARN if (over or under) else PASS,
        ("Parts of the face are blown out (pure white); this cannot be recovered. Retake with softer light."
         if over else "Parts of the face are nearly black; retake with more light on the face."
         if under else "Exposure looks natural."),
        stage=stage, basis="provisional", measured=f"clipped {stats.clipped * 100:.1f}%, dark {stats.crushed * 100:.1f}%",
        expected=f"each ≤ {p['clip_warn_fraction'] * 100:.0f}%", remedy="retake" if (over or under) else None,
    ))
    shadow = stats.asymmetry > p["asymmetry_warn_lightness"]
    checks.append(Check(
        f"{stage[:2]}.face_shadow", "lighting", "No shadow across the face",
        WARN if shadow else PASS,
        "One side of the face is much darker than the other (side lighting or shadow). "
        "This is not corrected automatically; retake facing a window or with even light." if shadow
        else "Lighting is even across the face.",
        stage=stage, basis="provisional", measured=stats.asymmetry, expected=f"≤ {p['asymmetry_warn_lightness']} L*",
        remedy="retake" if shadow else None,
    ))
    blurry = stats.sharpness < p["min_sharpness"]
    checks.append(Check(
        f"{stage[:2]}.sharpness", "lighting", "Photo is sharp",
        WARN if blurry else PASS,
        "The face looks blurry or low-contrast. Retake holding the camera steady." if blurry else "Face detail is sharp.",
        stage=stage, basis="provisional", measured=stats.sharpness, expected=f"≥ {p['min_sharpness']}",
        remedy="retake" if blurry else None,
    ))
    odd = stats.skin_chroma > 5 and not (0.0 <= stats.skin_hue_deg <= 100.0)
    checks.append(Check(
        f"{stage[:2]}.skin_tone", "lighting", "Natural skin tone (no colour cast)",
        WARN if odd else PASS,
        "Skin has an unusual colour cast (coloured lighting or white balance). Retake in daylight or neutral light."
        if odd else "No strong colour cast on the skin.",
        stage=stage, basis="provisional", measured=f"hue {stats.skin_hue_deg:.0f}°", expected="0–100°",
        remedy="retake" if odd else None,
    ))
    return checks
