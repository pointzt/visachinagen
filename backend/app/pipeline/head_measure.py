"""Head measurements (crown, chin, eyes, width) in the pixel space of the analysed image."""

from dataclasses import dataclass, replace

import numpy as np

from app.pipeline.face_analysis import FaceAnalysis


@dataclass
class HeadMeasure:
    crown_y: float
    chin_y: float
    eye_y: float
    center_x: float
    face_width: float
    inter_eye: float
    crown_source: str  # "silhouette" | "anatomical_voluminous_hair" | "anatomical_clipped"
    silhouette_crown_y: float | None
    anatomical_crown_y: float
    crown_clipped: bool

    @property
    def head_height(self) -> float:
        return self.chin_y - self.crown_y

    def trimmed_crown_y(self, hair_allowance: float) -> float:
        """Crown with voluminous hair trimmed (MFA allowance): at most a typical hair thickness
        above the anatomical crown. Never higher than the measured crown."""
        anat_h = self.chin_y - self.anatomical_crown_y
        return max(self.crown_y, self.anatomical_crown_y - hair_allowance * anat_h)

    def with_crown(self, crown_y: float, source: str) -> "HeadMeasure":
        return replace(self, crown_y=float(crown_y), crown_source=source)

    def as_dict(self) -> dict:
        return {
            "crown_y": round(self.crown_y, 1),
            "chin_y": round(self.chin_y, 1),
            "eye_y": round(self.eye_y, 1),
            "center_x": round(self.center_x, 1),
            "head_height_px": round(self.head_height, 1),
            "face_width_px": round(self.face_width, 1),
            "inter_eye_px": round(self.inter_eye, 1),
            "crown_source": self.crown_source,
            "crown_clipped": self.crown_clipped,
        }


def silhouette_top(fg: np.ndarray, x0: float, x1: float, y_limit: float, min_fraction: float = 0.15) -> tuple[float | None, bool]:
    """First row (from the top) where the head column band is at least ``min_fraction`` foreground.

    Returns ``(row, clipped)`` where ``clipped`` means the silhouette already touches the top edge.
    """
    h, w = fg.shape
    xa, xb = max(0, int(round(x0))), min(w, int(round(x1)))
    yb = max(1, min(h, int(round(y_limit))))
    if xb - xa < 2:
        return None, False
    band = fg[:yb, xa:xb]
    frac = band.mean(axis=1)
    rows = np.nonzero(frac >= min_fraction)[0]
    if rows.size == 0:
        return None, False
    top = int(rows[0])
    return float(top), top == 0


def measure_head(face: FaceAnalysis, fg: np.ndarray, policy: dict) -> HeadMeasure:
    """``fg`` is a boolean person mask in the same pixel space as ``face``."""
    crown_policy = policy["crown"]
    chin_y = float(face.chin[1])
    forehead_y = float(face.forehead_top[1])
    anat_height = max(1.0, (chin_y - forehead_y) * crown_policy["anatomical_ratio"])
    anat_crown = chin_y - anat_height

    cx, fw = face.center_x, face.face_width
    sil_crown, clipped = silhouette_top(fg, cx - 0.3 * fw, cx + 0.3 * fw, forehead_y)

    if sil_crown is None or clipped:
        crown, source = anat_crown - crown_policy["hair_allowance"] * anat_height, "anatomical_clipped"
    else:
        excess = (anat_crown - sil_crown) / anat_height
        if excess > crown_policy["voluminous_excess"]:
            crown, source = anat_crown - crown_policy["hair_allowance"] * anat_height, "anatomical_voluminous_hair"
        else:
            crown, source = sil_crown, "silhouette"

    return HeadMeasure(
        crown_y=float(crown),
        chin_y=chin_y,
        eye_y=float(face.eye_mid[1]),
        center_x=float(cx),
        face_width=float(fw),
        inter_eye=face.inter_eye_distance,
        crown_source=source,
        silhouette_crown_y=sil_crown,
        anatomical_crown_y=float(anat_crown),
        crown_clipped=clipped,
    )
