"""Crop solver: choose a uniform scale and translation that satisfies the document geometry.

The output is a similarity transform without rotation: ``out = s * src + (tx, ty)``. The solver
searches the scale range permitted by the spec (face width for digital, head height for paper),
closest to the spec target first, and for each scale intersects the linear constraints on
``ty``. Everything here is pure arithmetic so it is fully unit-tested.
"""

from dataclasses import dataclass, field

import numpy as np

from app.pipeline.head_measure import HeadMeasure
from app.pipeline.spec import Constraints

EYE_SAFETY_FRACTION = 0.01
# Plans aim this far inside every range so re-measuring the exported file (landmark jitter,
# JPEG) does not land on the wrong side of a limit.
RANGE_SAFETY_FRACTION = 0.012


@dataclass
class CropAdjust:
    scale: float = 1.0  # multiplier on the solved scale (manual zoom)
    offset_x: float = 0.0  # fraction of output width
    offset_y: float = 0.0  # fraction of output height

    @property
    def is_identity(self) -> bool:
        return abs(self.scale - 1) < 1e-6 and abs(self.offset_x) < 1e-6 and abs(self.offset_y) < 1e-6


@dataclass
class CropPlan:
    scale: float
    tx: float
    ty: float
    feasible: bool
    predicted: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    head: HeadMeasure | None = None  # the measurement the plan was solved for

    def source_rect(self, c: Constraints) -> tuple[float, float, float, float]:
        return (-self.tx / self.scale, -self.ty / self.scale, c.width / self.scale, c.height / self.scale)

    def as_dict(self) -> dict:
        return {"scale": round(self.scale, 5), "tx": round(self.tx, 2), "ty": round(self.ty, 2),
                "feasible": self.feasible, "predicted": {k: round(v, 2) for k, v in self.predicted.items()},
                "notes": self.notes}


def predict(head: HeadMeasure, s: float, tx: float, ty: float, c: Constraints) -> dict:
    return {
        "crown_to_top": s * head.crown_y + ty,
        "eye_line_to_bottom": c.height - (s * head.eye_y + ty),
        "chin_to_bottom": c.height - (s * head.chin_y + ty),
        "head_height": s * head.head_height,
        "face_width": s * head.face_width,
        "inter_eye_distance": s * head.inter_eye,
        "center_offset": s * head.center_x + tx - c.width / 2,
    }


def _ty_interval(head: HeadMeasure, s: float, c: Constraints) -> tuple[float, float]:
    lo, hi = -np.inf, np.inf
    ct = c.crown_to_top
    m = RANGE_SAFETY_FRACTION * c.height
    if ct.min is not None:
        lo = max(lo, ct.min + m - s * head.crown_y)
    if ct.max is not None:
        hi = min(hi, ct.max - m - s * head.crown_y)
    if c.eye_line_to_bottom is not None and c.eye_line_to_bottom.min is not None:
        # Safety margin so landmark jitter on re-measurement does not cross the limit.
        margin = EYE_SAFETY_FRACTION * c.height
        hi = min(hi, c.height - c.eye_line_to_bottom.min - margin - s * head.eye_y)
    if c.chin_to_bottom is not None and c.chin_to_bottom.min is not None:
        hi = min(hi, c.height - c.chin_to_bottom.min - s * head.chin_y)
    return lo, hi


def _violation(pred: dict, c: Constraints) -> float:
    total = 0.0
    for key in ("crown_to_top", "eye_line_to_bottom", "chin_to_bottom", "head_height", "face_width"):
        r = getattr(c, key, None)
        if r is None:
            continue
        v = pred[key]
        if r.min is not None and v < r.min:
            total += r.min - v
        if r.max is not None and v > r.max:
            total += v - r.max
    return total


def solve(head: HeadMeasure, c: Constraints, adjust: CropAdjust | None = None,
          hair_allowance: float | None = None) -> CropPlan:
    """Solve the layout. If it is infeasible because hair rises too high, retry with the hair
    trimmed at the top edge, which the MFA sheet explicitly permits for voluminous hair."""
    plan = _solve(head, c, adjust)
    if plan.feasible or hair_allowance is None or head.crown_source != "silhouette":
        return plan
    trimmed = head.trimmed_crown_y(hair_allowance)
    if trimmed - head.crown_y < 1.0:
        return plan
    retry = _solve(head.with_crown(trimmed, "hair_trimmed"), c, adjust)
    if retry.feasible:
        retry.notes.insert(0, "Voluminous hair trimmed at the top edge (allowed by the MFA rules) to keep the face at the required size.")
        retry.head = head.with_crown(trimmed, "hair_trimmed")
        return retry
    return plan


def _solve(head: HeadMeasure, c: Constraints, adjust: CropAdjust | None) -> CropPlan:
    metric = c.head_height if c.scale_metric == "head_height" else c.face_width
    base = head.head_height if c.scale_metric == "head_height" else head.face_width
    if base <= 0:
        raise ValueError("Head measurement is degenerate")
    s_target = metric.target / base
    span = metric.max - metric.min
    lo_m, hi_m = metric.min + RANGE_SAFETY_FRACTION * span * 2, metric.max - RANGE_SAFETY_FRACTION * span * 2
    candidates = np.linspace(lo_m / base, hi_m / base, 81)
    candidates = candidates[np.argsort(np.abs(candidates - s_target))]
    crown_target = c.crown_to_top.target if c.crown_to_top.target is not None else (c.crown_to_top.min + c.crown_to_top.max) / 2

    chosen = None
    for s in candidates:
        lo, hi = _ty_interval(head, float(s), c)
        if lo <= hi:
            ty = float(np.clip(crown_target - s * head.crown_y, lo, hi))
            chosen = (float(s), ty, True)
            break
    notes = []
    if chosen is None:
        # No geometry satisfies every rule: keep the target scale, minimise total violation.
        s = s_target
        lo, hi = _ty_interval(head, s, c)
        options = [crown_target - s * head.crown_y, lo, hi]
        options = [o for o in options if np.isfinite(o)]
        tx0 = c.width / 2 - s * head.center_x
        ty = min(options, key=lambda t: _violation(predict(head, s, tx0, t, c), c))
        chosen = (s, float(ty), False)
        notes.append("The head proportions in this photo cannot satisfy every rule at once.")

    s, ty, feasible = chosen
    tx = c.width / 2 - s * head.center_x

    if adjust is not None and not adjust.is_identity:
        # Zoom about the eye midpoint so manual zoom does not throw the face off-centre.
        ex, ey = s * head.center_x + tx, s * head.eye_y + ty
        s2 = s * adjust.scale
        tx = ex - s2 * head.center_x + adjust.offset_x * c.width
        ty = ey - s2 * head.eye_y + adjust.offset_y * c.height
        s = s2
        notes.append("Manual framing adjustment applied.")

    # Integer translation keeps the render and the prediction identical.
    tx, ty = float(round(tx)), float(round(ty))
    pred = predict(head, s, tx, ty, c)
    return CropPlan(scale=s, tx=tx, ty=ty, feasible=feasible and _violation(pred, c) == 0, predicted=pred,
                    notes=notes, head=head)
