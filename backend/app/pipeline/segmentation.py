"""Person segmentation (soft alpha) with BiRefNet-portrait via rembg.

Returns the model's soft matte rather than a composited image so rotation, cropping and
compositing can be done by the pipeline, and so the matte can be reused by /render.
"""

import io
import threading

import cv2
import numpy as np
from PIL import Image

_session = None
_lock = threading.Lock()


def _get_session():
    global _session
    if _session is None:
        from rembg import new_session
        _session = new_session("birefnet-portrait")
    return _session


def keep_main_subject(alpha: np.ndarray, anchor: tuple[float, float] | None = None) -> np.ndarray:
    """Zero out foreground blobs not connected to the main subject.

    The subject is the component containing ``anchor`` (e.g. the nose), else the largest one.
    """
    binary = (alpha > 25).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if n <= 2:
        return alpha
    keep = None
    if anchor is not None:
        x, y = int(round(anchor[0])), int(round(anchor[1]))
        if 0 <= y < labels.shape[0] and 0 <= x < labels.shape[1] and labels[y, x] > 0:
            keep = labels[y, x]
    if keep is None:
        keep = int(np.argmax(stats[1:, cv2.CC_STAT_AREA])) + 1
    return np.where(labels == keep, alpha, 0).astype(np.uint8)


def segment_person(rgb: np.ndarray) -> np.ndarray:
    """Soft alpha matte (uint8, 0..255) the same size as ``rgb``."""
    from rembg import remove

    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="PNG")
    with _lock:
        mask_bytes = remove(buf.getvalue(), session=_get_session(), only_mask=True, post_process_mask=False)
    mask = np.array(Image.open(io.BytesIO(mask_bytes)).convert("L"))
    if mask.shape != rgb.shape[:2]:
        mask = cv2.resize(mask, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_LINEAR)
    return mask


def encode_alpha(alpha: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(alpha, mode="L").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def decode_alpha(data: bytes, expected_size: tuple[int, int]) -> np.ndarray:
    mask = np.array(Image.open(io.BytesIO(data)).convert("L"))
    if (mask.shape[1], mask.shape[0]) != expected_size:
        raise ValueError(
            f"Mask size {mask.shape[1]}x{mask.shape[0]} does not match image {expected_size[0]}x{expected_size[1]}"
        )
    return mask
