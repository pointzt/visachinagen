"""Validate the exported file itself: re-decode the JPEG bytes and re-measure everything."""

import io

import cv2
import numpy as np
from PIL import Image

from app.pipeline import face_analysis
from app.pipeline.background_qa import check_output_background
from app.pipeline.checks import FAIL, PASS, UNVERIFIABLE, WARN, Check
from app.pipeline.color import delta_e, lab_of, rgb_to_lab
from app.pipeline.head_measure import measure_head
from app.pipeline.spec import MM_PER_INCH, Constraints, Range


def subject_mask_from_background(rgb: np.ndarray, bg_rgb: tuple[int, int, int], threshold: float = 10.0) -> np.ndarray:
    de = delta_e(rgb_to_lab(rgb), lab_of(bg_rgb))
    fg = (de > threshold).astype(np.uint8)
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    return fg.astype(bool)


def _geometry_check(cid: str, label: str, value: float, rng: Range | None, c: Constraints, unit_px: bool = True) -> Check | None:
    if rng is None:
        return None
    ok = rng.contains(value)
    if c.profile == "paper" and unit_px:
        shown = f"{value / (c.dpi / MM_PER_INCH):.1f} mm"
    elif c.reference_frame:
        rw, rh = c.reference_frame
        shown = f"{value * rh / c.height:.0f} px at {rw}×{rh} ({value:.0f} px in this image)"
    else:
        shown = f"{value:.0f} px"
    return Check(cid, "geometry", label, PASS if ok else FAIL,
                 f"{label}: {shown}." if ok else f"{label} is out of range: {shown}, required {rng.label}.",
                 basis=rng.status, measured=shown, expected=rng.label, remedy=None if ok else "adjust")


def validate_output(data: bytes, c: Constraints, spec: dict, policy: dict, bg_rgb: tuple[int, int, int],
                    render_alpha: np.ndarray | None, predicted: dict | None) -> tuple[list[Check], dict]:
    checks: list[Check] = []
    measured: dict = {}
    img = Image.open(io.BytesIO(data))
    img.load()
    w, h = img.size
    size_kb = len(data) / 1024.0
    measured.update({"width": w, "height": h, "file_size_kb": round(size_kb, 1)})

    # File format.
    if c.allowed_size:
        a = c.allowed_size
        ok = a["min_width_px"] <= w <= a["max_width_px"] and a["min_height_px"] <= h <= a["max_height_px"]
        expected = f"{a['min_width_px']}×{a['min_height_px']} to {a['max_width_px']}×{a['max_height_px']} px"
    else:
        ok = (w, h) == (c.width, c.height)
        expected = f"{c.width}×{c.height} px ({spec['profiles'][c.profile]['output'].get('width_mm')}×{spec['profiles'][c.profile]['output'].get('height_mm')} mm at {c.dpi} dpi)"
    checks.append(Check("out.dimensions", "file", "Image dimensions", PASS if ok else FAIL,
                        f"{w}×{h} px.", measured=f"{w}×{h}", expected=expected, remedy=None if ok else "adjust"))

    lo, hi = c.min_kb, c.max_kb
    ok = (lo is None or size_kb >= lo) and (hi is None or size_kb <= hi)
    checks.append(Check("out.file_size", "file", "File size", PASS if ok else FAIL, f"{size_kb:.0f} KB.",
                        measured=round(size_kb, 1), unit="KB",
                        expected=f"{lo:g}–{hi:g} KB" if lo is not None and hi is not None else "no limit",
                        remedy=None if ok else "adjust"))

    fmt_ok = img.format == "JPEG" and img.mode == "RGB"
    progressive = bool(img.info.get("progressive") or img.info.get("progression"))
    checks.append(Check("out.format", "file", "JPEG, 24-bit RGB colour", PASS if fmt_ok and not progressive else FAIL,
                        f"{img.format} {img.mode}{' (progressive)' if progressive else ''}.",
                        measured=f"{img.format} {img.mode}", expected="JPEG RGB"))
    dpi = img.info.get("dpi")
    exif = img.getexif()
    checks.append(Check("out.metadata", "file", "Clean metadata", PASS if not len(exif) else WARN,
                        f"DPI {round(dpi[0]) if dpi else 'unset'}; {'no' if not len(exif) else len(exif)} EXIF tags "
                        "(location and camera data removed).", basis="provisional"))
    measured["dpi"] = round(dpi[0]) if dpi else None

    rgb = np.array(img.convert("RGB"))
    face = face_analysis.analyze_face(rgb)
    if face is None:
        checks.append(Check("out.face", "face", "Face detected in final photo", FAIL,
                            "The face could not be re-detected in the exported photo, so its geometry cannot be verified.",
                            remedy="retake"))
        return checks, measured
    single = face.face_count == 1
    checks.append(Check("out.face", "face", "Exactly one face in final photo", PASS if single else FAIL,
                        "One face." if single else f"{face.face_count} faces detected in the final photo.",
                        remedy=None if single else "retake"))

    fg = subject_mask_from_background(rgb, bg_rgb)
    head = measure_head(face, fg, policy)
    m = {
        "crown_to_top": head.crown_y,
        "eye_line_to_bottom": h - head.eye_y,
        "chin_to_bottom": h - head.chin_y,
        "head_height": head.head_height,
        "face_width": head.face_width,
        "inter_eye_distance": head.inter_eye,
        "center_offset": head.center_x - w / 2,
    }
    measured["geometry_px"] = {k: round(v, 1) for k, v in m.items()}
    measured["crown_source"] = head.crown_source

    for cid, label, key, rng in (
        ("out.crown_to_top", "Top of head to upper edge", "crown_to_top", c.crown_to_top),
        ("out.eye_line", "Eye line to bottom edge", "eye_line_to_bottom", c.eye_line_to_bottom),
        ("out.face_width", "Face width", "face_width", c.face_width),
        ("out.inter_eye", "Distance between the eyes", "inter_eye_distance", c.inter_eye_distance),
        ("out.head_height", "Head height (chin to crown)", "head_height", c.head_height),
        ("out.chin_to_bottom", "Chin to bottom edge", "chin_to_bottom", c.chin_to_bottom),
    ):
        chk = _geometry_check(cid, label, m[key], rng, c)
        if chk and key == "crown_to_top" and chk.status == FAIL and head.crown_source == "silhouette" \
                and m[key] < rng.min:
            # Hair rises above the allowed clearance. The MFA sheet lets voluminous hair be
            # trimmed at the top edge, so evaluate the crown with hair trimmed.
            trimmed = head.trimmed_crown_y(policy["crown"]["hair_allowance"])
            alt = _geometry_check(cid, label, trimmed, rng, c)
            if alt.status == PASS:
                alt.basis = "provisional"
                alt.message += (" Hair rises above this line; it counts as voluminous hair that may be trimmed "
                                "at the top edge under the MFA rules. Confirm visually.")
                chk = alt
                measured["crown_source"] = "hair_trimmed"
        if chk:
            if key == "crown_to_top" and head.crown_source != "silhouette":
                chk.message += " Crown estimated from facial proportions because the hair reaches the top edge (MFA allows trimming voluminous hair)."
                if chk.status == PASS:
                    chk.basis = "provisional"
            checks.append(chk)

    if c.head_width is not None:
        # Landmark face width is cheek-to-cheek; the paper rule is whole-head width, which is
        # usually a little wider, so this is a warning-level check.
        hw = _geometry_check("out.head_width", "Head width", head.face_width, c.head_width, c)
        if hw.status == FAIL:
            hw.status = WARN
        hw.basis = "provisional"
        checks.append(hw)

    off = abs(m["center_offset"])
    ok = off <= c.center_tolerance_px
    checks.append(Check("out.centered", "geometry", "Head horizontally centred", PASS if ok else FAIL,
                        f"Offset {off:.0f} px from centre.", basis=c.center_tolerance_status, measured=round(off, 1),
                        expected=f"≤ {c.center_tolerance_px:.0f} px", remedy=None if ok else "adjust"))

    # Pose re-check on the delivered image (official limits).
    lim = spec["pose_limits"]
    for key, label, value, limit in (
        ("yaw", "Head turned left/right (yaw)", face.yaw_deg, lim["max_abs_yaw_deg"]),
        ("pitch", "Head up/down (pitch)", face.pitch_deg, lim["max_abs_pitch_deg"]),
        ("roll", "Head tilt (roll)", face.eye_roll_deg, lim["max_abs_roll_deg"]),
    ):
        ok = abs(value) <= limit
        checks.append(Check(f"out.pose_{key}", "pose", label, PASS if ok else FAIL,
                            f"{value:+.1f}°.", measured=round(value, 1), unit="°", expected=f"≤ {limit}°",
                            remedy=None if ok else "retake"))
    measured["pose"] = {"yaw": round(face.yaw_deg, 1), "pitch": round(face.pitch_deg, 1), "roll": round(face.eye_roll_deg, 2)}

    checks.extend(check_output_background(rgb, fg, bg_rgb, spec["background"], render_alpha, policy))

    if predicted:
        tol = policy["output_measurement_tolerance"] * h
        drift = {k: abs(m[k] - predicted[k]) for k in ("crown_to_top", "eye_line_to_bottom", "chin_to_bottom") if k in predicted}
        worst_key = max(drift, key=drift.get)
        ok = drift[worst_key] <= tol
        checks.append(Check("out.measurement_agreement", "geometry", "Re-measurement agrees with the plan",
                            PASS if ok else WARN,
                            "Measurements of the exported file match the planned layout." if ok
                            else f"The exported file measures {drift[worst_key]:.0f} px differently from the plan ({worst_key}); "
                                 "treat the geometry as uncertain and check it visually.",
                            basis="provisional", measured=round(drift[worst_key], 1), expected=f"≤ {tol:.0f} px"))
    return checks, measured


def checklist_items() -> list[Check]:
    """Rules that cannot be verified automatically; shown for the user to confirm."""
    items = [
        ("chk.glasses", "Glasses: lenses not tinted, no glare, frames do not cover the eyes"),
        ("chk.head_covering", "No hat or head covering (religious coverings must not hide facial features)"),
        ("chk.jewellery", "No jewellery or ornaments that distract; no hands, toys or other people"),
        ("chk.ears", "Ears visible; hair does not cover eyebrows or eyes"),
        ("chk.recent", "Photo taken within the last 6 months"),
        ("chk.red_eye", "No red-eye"),
    ]
    return [Check(i, "checklist", label, UNVERIFIABLE, "Please confirm this yourself.", basis="verified") for i, label in items]
