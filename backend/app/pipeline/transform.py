"""Rigid (rotation-only) transforms. No local warping is ever applied to the face."""

import cv2
import numpy as np


def rotation_matrix(center: tuple[float, float], angle_deg: float, size: tuple[int, int]) -> tuple[np.ndarray, tuple[int, int]]:
    """Affine matrix rotating by ``angle_deg`` (OpenCV convention: positive = counter-clockwise
    on screen) about ``center``, with the canvas expanded so no source pixel is lost."""
    w, h = size
    m = cv2.getRotationMatrix2D(center, angle_deg, 1.0)
    corners = np.array([[0, 0, 1], [w, 0, 1], [0, h, 1], [w, h, 1]], dtype=np.float64)
    moved = corners @ m.T
    x0, y0 = moved.min(axis=0)
    x1, y1 = moved.max(axis=0)
    m[0, 2] -= x0
    m[1, 2] -= y0
    return m, (int(np.ceil(x1 - x0)), int(np.ceil(y1 - y0)))


def rotate(rgb: np.ndarray, alpha: np.ndarray | None, angle_deg: float, center: tuple[float, float]):
    """Rotate image and matte together.

    Returns ``(rgb, alpha, valid, matrix)`` where ``valid`` marks pixels that came from the
    source (255) versus the empty corners introduced by rotation (0).
    """
    h, w = rgb.shape[:2]
    m, (nw, nh) = rotation_matrix(center, angle_deg, (w, h))
    out = cv2.warpAffine(rgb, m, (nw, nh), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    valid = cv2.warpAffine(np.full((h, w), 255, np.uint8), m, (nw, nh), flags=cv2.INTER_NEAREST,
                           borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    a = None
    if alpha is not None:
        a = cv2.warpAffine(alpha, m, (nw, nh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    return out, a, valid, m


def transform_points(points: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    pts = np.asarray(points, dtype=np.float64).reshape(-1, 2)
    return np.hstack([pts, np.ones((len(pts), 1))]) @ matrix.T
