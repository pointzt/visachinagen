"""Colour helpers: sRGB <-> linear, CIELAB, CIE76 delta E."""

import cv2
import numpy as np


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    c = color.lstrip("#")
    if len(c) != 6:
        raise ValueError(f"Invalid colour: {color}")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def srgb_to_linear(x: np.ndarray) -> np.ndarray:
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1 / 2.4) - 0.055)


def rgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """uint8 or float [0,1] RGB -> float32 Lab (L 0..100)."""
    arr = rgb.astype(np.float32)
    if rgb.dtype == np.uint8:
        arr /= 255.0
    return cv2.cvtColor(arr.reshape(-1, 1, 3) if arr.ndim == 2 else arr, cv2.COLOR_RGB2LAB).reshape(arr.shape)


def delta_e(lab: np.ndarray, ref_lab: np.ndarray) -> np.ndarray:
    return np.linalg.norm(lab - np.asarray(ref_lab, dtype=np.float32), axis=-1)


def lab_of(color: tuple[int, int, int]) -> np.ndarray:
    return rgb_to_lab(np.array([[color]], dtype=np.uint8))[0, 0]
