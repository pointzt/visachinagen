"""Separate camera tilt from head tilt.

A single photo cannot always tell the two apart. The eye line measures head roll relative to
the camera. Independent references are needed to decide whether the *camera* was rotated:

* straight lines in the background (door frames, wall edges) — strong evidence;
* the shoulder line from MediaPipe Pose — weak evidence (people often stand unevenly).

All angles use one convention: degrees, positive = clockwise on screen (right end lower /
top leaning right). Rotating with OpenCV by the same positive angle (counter-clockwise)
cancels it.
"""

import math
from dataclasses import dataclass, field

import cv2
import numpy as np

from app.pipeline import models

LEFT_SHOULDER, RIGHT_SHOULDER = 11, 12


@dataclass
class Reference:
    source: str  # "scene_lines" | "shoulders"
    angle_deg: float
    confidence: float
    detail: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"source": self.source, "angle_deg": round(self.angle_deg, 2),
                "confidence": round(self.confidence, 2), **self.detail}


@dataclass
class TiltDecision:
    classification: str  # level | camera_tilt | head_tilt | ambiguous
    confidence: float
    angle_deg: float  # rotation that would correct the tilt (0 when none)
    auto_apply: bool
    suggest: bool
    reason: str
    evidence: list[Reference] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "classification": self.classification,
            "confidence": round(self.confidence, 2),
            "angle_deg": round(self.angle_deg, 2),
            "auto_apply": self.auto_apply,
            "suggest": self.suggest,
            "reason": self.reason,
            "evidence": [e.as_dict() for e in self.evidence],
        }


def _line_tilt(x1: float, y1: float, x2: float, y2: float) -> tuple[str, float]:
    """Classify a segment as near-horizontal/vertical and return its tilt in the shared convention."""
    dx, dy = x2 - x1, y2 - y1
    ang = math.degrees(math.atan2(dy, dx))
    ang = (ang + 90) % 180 - 90  # (-90, 90]
    if abs(ang) <= 45:
        return "h", ang
    # Vertical: measure how far the top end leans right.
    if y1 > y2:
        x1, y1, x2, y2 = x2, y2, x1, y1  # (x1, y1) is now the top end
    return "v", math.degrees(math.atan2(x1 - x2, y2 - y1))


def scene_line_reference(rgb: np.ndarray, alpha: np.ndarray, min_lines: int = 2,
                         max_dev_deg: float = 12.0) -> Reference | None:
    """Estimate camera roll from long straight lines in the background only."""
    h, w = alpha.shape
    diag = math.hypot(w, h)
    bg = (alpha < 20).astype(np.uint8)
    margin = max(3, int(diag * 0.015))
    bg = cv2.erode(bg, np.ones((margin * 2 + 1, margin * 2 + 1), np.uint8))
    bg[:4, :] = bg[-4:, :] = 0
    bg[:, :4] = bg[:, -4:] = 0
    if bg.mean() < 0.05:
        return None

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    med = float(np.median(gray))
    edges = cv2.Canny(gray, max(10, 0.66 * med), min(255, 1.33 * med + 20))
    edges[bg == 0] = 0
    min_len = 0.12 * min(w, h)
    segs = cv2.HoughLinesP(edges, 1, np.pi / 720, threshold=int(min_len * 0.5),
                           minLineLength=min_len, maxLineGap=4)
    if segs is None:
        return None

    tilts, lengths = [], []
    for x1, y1, x2, y2 in segs[:, 0, :].astype(float):
        _, t = _line_tilt(x1, y1, x2, y2)
        if abs(t) <= max_dev_deg:
            tilts.append(t)
            lengths.append(math.hypot(x2 - x1, y2 - y1))
    if len(tilts) < min_lines:
        return None
    tilts, lengths = np.array(tilts), np.array(lengths)
    order = np.argsort(tilts)
    cum = np.cumsum(lengths[order])
    median = float(tilts[order][np.searchsorted(cum, cum[-1] / 2)])
    near = np.abs(tilts - median) <= 1.5
    support = float(lengths[near].sum() / lengths.sum())
    if near.sum() < min_lines or support < 0.5:
        return None
    angle = float(np.average(tilts[near], weights=lengths[near]))
    return Reference("scene_lines", angle, support, {"lines": int(near.sum())})


def shoulder_reference(rgb: np.ndarray, min_visibility: float = 0.8) -> Reference | None:
    result = models.run("pose_landmarker", rgb)
    if not result.pose_landmarks:
        return None
    lms = result.pose_landmarks[0]
    h, w = rgb.shape[:2]
    pts = []
    for idx in (LEFT_SHOULDER, RIGHT_SHOULDER):
        lm = lms[idx]
        vis = min(getattr(lm, "visibility", 0.0) or 0.0, getattr(lm, "presence", 1.0) or 0.0)
        if vis < min_visibility or not (0.01 < lm.x < 0.99 and 0.01 < lm.y < 0.99):
            return None
        pts.append((lm.x * w, lm.y * h, vis))
    (ax, ay, av), (bx, by, bv) = sorted(pts, key=lambda p: p[0])
    angle = math.degrees(math.atan2(by - ay, bx - ax))
    return Reference("shoulders", angle, min(av, bv))


def decide_tilt(eye_roll_deg: float, face_confidence: float, scene: Reference | None,
                shoulders: Reference | None, policy: dict) -> TiltDecision:
    level = policy["level_threshold_deg"]
    tol = policy["agreement_tolerance_deg"]
    ref_level = policy["reference_level_deg"]
    max_auto = policy["max_auto_rotate_deg"]
    confident_face = face_confidence >= policy.get("review_face_confidence", 0.85)
    r = eye_roll_deg
    evidence = [e for e in (scene, shoulders) if e is not None]

    if abs(r) < level:
        return TiltDecision("level", 0.9, 0.0, False, False,
                            f"Eyes are level ({r:+.1f}°).", evidence)

    def within_limits(angle: float) -> bool:
        return abs(angle) <= max_auto

    if scene is not None:
        if abs(scene.angle_deg - r) <= tol and abs(scene.angle_deg) >= level:
            angle = scene.angle_deg
            auto = confident_face and within_limits(angle)
            return TiltDecision(
                "camera_tilt", min(0.95, 0.5 + 0.45 * scene.confidence), angle, auto, not auto,
                f"Background lines are tilted {scene.angle_deg:+.1f}°, matching the eye line ({r:+.1f}°): the camera was rotated.",
                evidence)
        if abs(scene.angle_deg) < ref_level:
            return TiltDecision(
                "head_tilt", min(0.9, 0.5 + 0.4 * scene.confidence), 0.0, False, False,
                f"Background lines are level but the eye line is {r:+.1f}°: the head is tilted, not the camera.",
                evidence)

    if shoulders is not None:
        if abs(shoulders.angle_deg - r) <= tol and abs(shoulders.angle_deg) >= level:
            angle = (shoulders.angle_deg + r) / 2.0
            auto = policy.get("auto_rotate_on_shoulder_agreement", False) and confident_face and within_limits(angle)
            return TiltDecision(
                "camera_tilt", 0.6 * shoulders.confidence, angle, auto, not auto,
                f"Shoulders ({shoulders.angle_deg:+.1f}°) and eyes ({r:+.1f}°) are tilted together. "
                "This usually means the camera was rotated, but the whole body may be leaning.",
                evidence)
        if abs(shoulders.angle_deg) < ref_level:
            return TiltDecision(
                "head_tilt", 0.65 * shoulders.confidence, 0.0, False, False,
                f"Shoulders are level but the eye line is {r:+.1f}°: the head appears tilted.",
                evidence)

    return TiltDecision(
        "ambiguous", 0.3, r, False, within_limits(r),
        f"The eye line is tilted {r:+.1f}°, but there is no reliable reference to tell camera tilt from head tilt.",
        evidence)
