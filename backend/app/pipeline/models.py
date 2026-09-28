"""Lazy, thread-safe access to the ML models used by the pipeline.

MediaPipe task objects are not safe to call concurrently, and FastAPI runs sync endpoints in a
thread pool, so every inference call is guarded by a per-model lock.
"""

import os
import threading
import urllib.request

import mediapipe as mp
import numpy as np

_MODELS = {
    "face_landmarker": (
        "face_landmarker.task",
        "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task",
    ),
    "face_detector": (
        "blaze_face_short_range.tflite",
        "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite",
    ),
    "pose_landmarker": (
        "pose_landmarker_lite.task",
        "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task",
    ),
}

_SEARCH_DIRS = [
    os.environ.get("PHOTOGEN_MODEL_DIR", ""),
    os.path.join(os.path.expanduser("~"), "models"),
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core", "models"),
]

_instances: dict = {}
_locks = {name: threading.Lock() for name in _MODELS}
_init_lock = threading.Lock()


def model_path(name: str, download: bool = True) -> str | None:
    filename, url = _MODELS[name]
    for d in _SEARCH_DIRS:
        if d and os.path.exists(os.path.join(d, filename)):
            return os.path.join(d, filename)
    if not download:
        return None
    target_dir = next(d for d in _SEARCH_DIRS if d)
    os.makedirs(target_dir, exist_ok=True)
    target = os.path.join(target_dir, filename)
    urllib.request.urlretrieve(url, target)
    return target


def models_available() -> dict[str, bool]:
    return {name: model_path(name, download=False) is not None for name in _MODELS}


def _create(name: str):
    vision = mp.tasks.vision
    base = mp.tasks.BaseOptions(model_asset_path=model_path(name))
    if name == "face_landmarker":
        return vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
            base_options=base,
            num_faces=4,
            min_face_detection_confidence=0.4,
            min_face_presence_confidence=0.4,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
        ))
    if name == "face_detector":
        return vision.FaceDetector.create_from_options(vision.FaceDetectorOptions(
            base_options=base, min_detection_confidence=0.3,
        ))
    if name == "pose_landmarker":
        return vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(
            base_options=base, num_poses=1,
        ))
    raise KeyError(name)


def _get(name: str):
    if name not in _instances:
        with _init_lock:
            if name not in _instances:
                _instances[name] = _create(name)
    return _instances[name]


def run(name: str, rgb: np.ndarray):
    """Run a MediaPipe task on an RGB uint8 array."""
    model = _get(name)
    image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
    with _locks[name]:
        return model.detect(image)
