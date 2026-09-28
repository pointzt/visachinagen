"""Versioned document specifications.

Specs live in ``shared/specs/<id>.v<major>.json``. Every numeric requirement carries a
``status`` of ``verified`` (stated by the issuing authority) or ``provisional`` (a PhotoGen
engineering threshold). Measurements are converted here into output-pixel constraints so the
geometry solver and the output validator share one source of truth.
"""

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache

MM_PER_INCH = 25.4


def _find_specs_dir() -> str:
    """``PHOTOGEN_SPECS_DIR`` wins; otherwise the nearest ``shared/specs`` above this file
    (the repo layout; a Docker build from ``backend/`` must copy ``shared/`` in the same way
    as ``shared/photo_requirements.json``)."""
    env = os.environ.get("PHOTOGEN_SPECS_DIR")
    if env:
        return env
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):
        candidate = os.path.join(d, "shared", "specs")
        if os.path.isdir(candidate):
            return candidate
        d = os.path.dirname(d)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../shared/specs")


SPECS_DIR = _find_specs_dir()


@dataclass(frozen=True)
class Range:
    min: float | None = None
    max: float | None = None
    target: float | None = None
    exclusive_min: bool = False
    status: str = "verified"
    label: str = ""

    def contains(self, value: float) -> bool:
        if self.min is not None:
            if self.exclusive_min and value <= self.min:
                return False
            if not self.exclusive_min and value < self.min:
                return False
        if self.max is not None and value > self.max:
            return False
        return True


@dataclass(frozen=True)
class Constraints:
    """Requirements expressed in output pixels for one profile."""

    profile: str
    width: int
    height: int
    dpi: int
    crown_to_top: Range
    face_width: Range | None = None
    head_height: Range | None = None
    head_width: Range | None = None
    eye_line_to_bottom: Range | None = None
    chin_to_bottom: Range | None = None
    inter_eye_distance: Range | None = None
    center_tolerance_px: float = 0.0
    center_tolerance_status: str = "provisional"
    min_kb: float | None = None
    max_kb: float | None = None
    allowed_size: dict = field(default_factory=dict)
    scale_metric: str = "face_width"
    reference_frame: tuple[int, int] | None = None


def list_specs() -> list[str]:
    return sorted(f.split(".")[0] for f in os.listdir(SPECS_DIR) if f.endswith(".json"))


@lru_cache(maxsize=8)
def load_spec(spec_id: str = "CHINA_VISA", major: int = 1) -> dict:
    if not os.path.isdir(SPECS_DIR):
        raise RuntimeError(f"Specification directory not found: {SPECS_DIR}. Set PHOTOGEN_SPECS_DIR.")
    path = os.path.join(SPECS_DIR, f"{spec_id.lower()}.v{major}.json")
    if not os.path.exists(path):
        raise ValueError(f"Unknown specification: {spec_id} v{major}")
    with open(path, "r") as f:
        spec = json.load(f)
    if "profiles" not in spec or "version" not in spec:
        raise ValueError(f"Malformed specification file: {path}")
    return spec


def _fmt(v: float) -> str:
    return f"{v:g}"


def _range(entry: dict, scale: float, unit_label: str) -> Range:
    lo = entry.get("min", entry.get("min_exclusive"))
    hi = entry.get("max")
    tgt = entry.get("target")
    exclusive = "min_exclusive" in entry
    if lo is not None and hi is not None:
        label = f"{_fmt(lo)}–{_fmt(hi)} {unit_label}"
    elif lo is not None:
        label = f"{'>' if exclusive else '≥'} {_fmt(lo)} {unit_label}"
    else:
        label = f"≤ {_fmt(hi)} {unit_label}"
    return Range(
        min=None if lo is None else lo * scale,
        max=None if hi is None else hi * scale,
        target=None if tgt is None else tgt * scale,
        exclusive_min=exclusive,
        status=entry.get("status", "verified"),
        label=label,
    )


def _fraction_range(entry: dict, total: float) -> Range:
    lo = entry.get("min")
    return Range(min=lo * total, status=entry.get("status", "provisional"), label=f"≥ {lo * 100:g}% of height")


def constraints_for(spec: dict, profile: str) -> Constraints:
    if profile not in spec["profiles"]:
        raise ValueError(f"Unknown profile '{profile}'. Available: {', '.join(spec['profiles'])}")
    p = spec["profiles"][profile]
    geo = p["geometry"]
    out = p["output"]
    file_req = p.get("file", {})

    if "width_px" in out:
        width, height = int(out["width_px"]), int(out["height_px"])
    else:
        width = round(out["width_mm"] / MM_PER_INCH * out["dpi"])
        height = round(out["height_mm"] / MM_PER_INCH * out["dpi"])
    dpi = int(out.get("dpi", 300))

    ref = p.get("reference_frame")
    if ref:
        ref_scale = height / ref["height_px"]
        unit_label = f"px at {ref['width_px']}×{ref['height_px']}"
    else:
        ref_scale = None
        unit_label = ""
    px_per_mm = dpi / MM_PER_INCH

    def conv(key: str) -> Range | None:
        entry = geo.get(key)
        if entry is None:
            return None
        unit = entry.get("unit")
        if unit == "ref_px":
            return _range(entry, ref_scale, unit_label)
        if unit == "mm":
            return _range(entry, px_per_mm, "mm")
        if unit == "fraction_of_height":
            return _fraction_range(entry, height)
        raise ValueError(f"Unsupported unit '{unit}' for {key}")

    center = geo.get("horizontal_center_tolerance", {"value": 0.03, "status": "provisional"})
    return Constraints(
        profile=profile,
        width=width,
        height=height,
        dpi=dpi,
        crown_to_top=conv("crown_to_top"),
        face_width=conv("face_width"),
        head_height=conv("head_height"),
        head_width=conv("head_width"),
        eye_line_to_bottom=conv("eye_line_to_bottom"),
        chin_to_bottom=conv("chin_to_bottom"),
        inter_eye_distance=conv("inter_eye_distance"),
        center_tolerance_px=center["value"] * width,
        center_tolerance_status=center.get("status", "provisional"),
        min_kb=file_req.get("min_kb"),
        max_kb=file_req.get("max_kb"),
        allowed_size=p.get("allowed_size", {}),
        scale_metric="head_height" if "head_height" in geo else "face_width",
        reference_frame=(ref["width_px"], ref["height_px"]) if ref else None,
    )


def spec_summary(spec: dict) -> dict:
    return {
        "id": spec["id"],
        "version": spec["version"],
        "name": spec["name"],
        "source": spec["source"],
        "profiles": {k: v["label"] for k, v in spec["profiles"].items()},
    }
