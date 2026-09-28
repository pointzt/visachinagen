"""Face landmarks, head pose and expression from MediaPipe Face Landmarker.

Everything returned is a measurement of the photo as captured. Nothing here modifies pixels.
"""

import math
from dataclasses import dataclass, field

import numpy as np

from app.pipeline import models

# MediaPipe Face Mesh topology (478 points with iris refinement).
FACE_OVAL = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377,
             152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]
IRIS_CENTERS = (468, 473)
CHIN = 152
FOREHEAD_TOP = 10
CHEEK_EXTREMES = (234, 454)
NOSE_TIP = 1


@dataclass
class FaceAnalysis:
    image_size: tuple[int, int]
    landmarks: np.ndarray  # (478, 2) pixel coordinates
    left_eye: np.ndarray  # image-left iris centre
    right_eye: np.ndarray
    eye_roll_deg: float  # positive = image-right eye lower (clockwise tilt on screen)
    yaw_deg: float
    pitch_deg: float
    roll_deg: float  # from the 3D transformation matrix, same sign convention as eye_roll_deg
    blendshapes: dict[str, float]
    confidence: float
    face_count: int
    secondary_face_ratio: float = 0.0
    warnings: list[str] = field(default_factory=list)

    @property
    def eye_mid(self) -> np.ndarray:
        return (self.left_eye + self.right_eye) / 2.0

    @property
    def inter_eye_distance(self) -> float:
        return float(np.linalg.norm(self.right_eye - self.left_eye))

    @property
    def chin(self) -> np.ndarray:
        return self.landmarks[CHIN]

    @property
    def forehead_top(self) -> np.ndarray:
        return self.landmarks[FOREHEAD_TOP]

    @property
    def face_width(self) -> float:
        a, b = self.landmarks[CHEEK_EXTREMES[0]], self.landmarks[CHEEK_EXTREMES[1]]
        return float(np.linalg.norm(b - a))

    @property
    def center_x(self) -> float:
        a, b = self.landmarks[CHEEK_EXTREMES[0]], self.landmarks[CHEEK_EXTREMES[1]]
        return float((a[0] + b[0]) / 2.0)

    @property
    def oval(self) -> np.ndarray:
        return self.landmarks[FACE_OVAL]

    def summary(self) -> dict:
        return {
            "confidence": round(self.confidence, 3),
            "face_count": self.face_count,
            "eye_roll_deg": round(self.eye_roll_deg, 2),
            "yaw_deg": round(self.yaw_deg, 1),
            "pitch_deg": round(self.pitch_deg, 1),
            "roll_deg": round(self.roll_deg, 1),
            "inter_eye_px": round(self.inter_eye_distance, 1),
            "face_width_px": round(self.face_width, 1),
            "expression": {k: round(v, 2) for k, v in self.blendshapes.items()
                           if k in ("eyeBlinkLeft", "eyeBlinkRight", "jawOpen", "mouthSmileLeft", "mouthSmileRight")},
        }


def euler_from_matrix(matrix: np.ndarray) -> tuple[float, float, float]:
    """Decompose a MediaPipe facial transformation matrix into (yaw, pitch, roll) degrees.

    The matrix maps the canonical face model (x right, y up, z toward the camera) into camera
    space. Roll is negated so that it follows the image convention used for ``eye_roll_deg``
    (y axis pointing down).
    """
    r = np.asarray(matrix, dtype=np.float64)[:3, :3]
    r = r / np.linalg.norm(r, axis=0, keepdims=True)
    sy = math.hypot(r[0, 0], r[1, 0])
    if sy > 1e-6:
        pitch = math.atan2(r[2, 1], r[2, 2])
        yaw = math.atan2(-r[2, 0], sy)
        roll = math.atan2(r[1, 0], r[0, 0])
    else:
        pitch = math.atan2(-r[1, 2], r[1, 1])
        yaw = math.atan2(-r[2, 0], sy)
        roll = 0.0
    return math.degrees(yaw), math.degrees(pitch), -math.degrees(roll)


def eye_roll(left_eye: np.ndarray, right_eye: np.ndarray) -> float:
    dx, dy = right_eye[0] - left_eye[0], right_eye[1] - left_eye[1]
    return math.degrees(math.atan2(dy, dx))


def _detector_confidence(rgb: np.ndarray, face_box: tuple[float, float, float, float]) -> float | None:
    """Score of the BlazeFace detection that overlaps the landmarked face, if any."""
    result = models.run("face_detector", rgb)
    fx0, fy0, fx1, fy1 = face_box
    best = None
    for det in result.detections:
        bb = det.bounding_box
        x0, y0, x1, y1 = bb.origin_x, bb.origin_y, bb.origin_x + bb.width, bb.origin_y + bb.height
        ix = max(0.0, min(x1, fx1) - max(x0, fx0))
        iy = max(0.0, min(y1, fy1) - max(y0, fy0))
        inter = ix * iy
        union = (x1 - x0) * (y1 - y0) + (fx1 - fx0) * (fy1 - fy0) - inter
        if union > 0 and inter / union > 0.3:
            score = det.categories[0].score
            best = score if best is None else max(best, score)
    return best


def analyze_face(rgb: np.ndarray) -> FaceAnalysis | None:
    """Return the analysis of the largest face, or None when no face is found."""
    h, w = rgb.shape[:2]
    result = models.run("face_landmarker", rgb)
    if not result.face_landmarks:
        return None

    faces = []
    for idx, lms in enumerate(result.face_landmarks):
        pts = np.array([[lm.x * w, lm.y * h] for lm in lms], dtype=np.float64)
        width = float(pts[:, 0].max() - pts[:, 0].min())
        faces.append((width, idx, pts))
    faces.sort(key=lambda f: f[0], reverse=True)
    primary_width, primary_idx, pts = faces[0]
    secondary_ratio = faces[1][0] / primary_width if len(faces) > 1 else 0.0

    a, b = pts[IRIS_CENTERS[0]], pts[IRIS_CENTERS[1]]
    left_eye, right_eye = (a, b) if a[0] <= b[0] else (b, a)

    yaw = pitch = roll = 0.0
    if result.facial_transformation_matrixes:
        yaw, pitch, roll = euler_from_matrix(result.facial_transformation_matrixes[primary_idx])

    blend = {}
    if result.face_blendshapes:
        blend = {c.category_name: float(c.score) for c in result.face_blendshapes[primary_idx]}

    box = (pts[:, 0].min(), pts[:, 1].min(), pts[:, 0].max(), pts[:, 1].max())
    warnings = []
    det_conf = _detector_confidence(rgb, box)
    if det_conf is None:
        # The landmarker found a face the detector did not confirm: usable, but flagged.
        confidence = 0.6
        warnings.append("Face detector did not independently confirm the face.")
    else:
        confidence = float(det_conf)

    return FaceAnalysis(
        image_size=(w, h),
        landmarks=pts,
        left_eye=left_eye,
        right_eye=right_eye,
        eye_roll_deg=eye_roll(left_eye, right_eye),
        yaw_deg=yaw,
        pitch_deg=pitch,
        roll_deg=roll,
        blendshapes=blend,
        confidence=confidence,
        face_count=len(faces),
        secondary_face_ratio=secondary_ratio,
        warnings=warnings,
    )
