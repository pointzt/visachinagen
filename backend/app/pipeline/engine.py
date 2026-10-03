"""China visa photo engine: analyse -> correct -> render -> validate the exported file.

Every automatic change is recorded as a *correction* the user can undo, and every requirement
as a *check* with the stage it was measured at and whether its threshold is official
(``verified``) or a PhotoGen engineering choice (``provisional``).
"""

import base64
import io
import time
from dataclasses import dataclass, field

import cv2
import numpy as np
import pillow_heif
from PIL import Image, ImageOps

from app.pipeline import face_analysis, lighting, segmentation, tilt, transform
from app.pipeline.background_qa import check_kept_background, check_matte
from app.pipeline.checks import FAIL, PASS, WARN, Check
from app.pipeline.color import hex_to_rgb
from app.pipeline.geometry import CropAdjust, solve
from app.pipeline.head_measure import measure_head
from app.pipeline.output_validator import checklist_items, validate_output
from app.pipeline.render import encode_jpeg, render
from app.pipeline.spec import constraints_for, load_spec, spec_summary

pillow_heif.register_heif_opener()

MAX_MANUAL_ROTATION = 15.0


@dataclass
class Overrides:
    rotation: str = "auto"  # auto | off | manual
    rotation_deg: float = 0.0
    replace_background: bool = True
    edge_refine: bool = True
    lighting: str = "auto"  # auto | off | manual
    exposure_ev: float = 0.0
    contrast: float = 0.0
    crop: CropAdjust = field(default_factory=CropAdjust)

    @classmethod
    def from_dict(cls, d: dict | None) -> "Overrides":
        d = d or {}
        crop = d.get("crop") or {}
        o = cls(
            rotation=d.get("rotation", "auto"),
            rotation_deg=float(d.get("rotation_deg", 0.0) or 0.0),
            replace_background=bool(d.get("replace_background", True)),
            edge_refine=bool(d.get("edge_refine", True)),
            lighting=d.get("lighting", "auto"),
            exposure_ev=float(d.get("exposure_ev", 0.0) or 0.0),
            contrast=float(d.get("contrast", 0.0) or 0.0),
            crop=CropAdjust(
                scale=float(np.clip(crop.get("scale", 1.0), 0.8, 1.25)),
                offset_x=float(np.clip(crop.get("offset_x", 0.0), -0.15, 0.15)),
                offset_y=float(np.clip(crop.get("offset_y", 0.0), -0.15, 0.15)),
            ),
        )
        if o.rotation not in ("auto", "off", "manual"):
            raise ValueError("rotation must be auto, off or manual")
        if o.lighting not in ("auto", "off", "manual"):
            raise ValueError("lighting must be auto, off or manual")
        o.rotation_deg = float(np.clip(o.rotation_deg, -MAX_MANUAL_ROTATION, MAX_MANUAL_ROTATION))
        return o


def _b64_jpeg(rgb: np.ndarray, max_side: int = 900, quality: int = 88) -> str:
    img = Image.fromarray(rgb)
    img.thumbnail((max_side, max_side), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode()


def decode_image(image_bytes: bytes, max_side: int) -> np.ndarray:
    img = Image.open(io.BytesIO(image_bytes))
    img = ImageOps.exif_transpose(img).convert("RGB")
    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.LANCZOS)
    return np.array(img)


def _mask_preview(rgb: np.ndarray, alpha: np.ndarray) -> str:
    a = (alpha.astype(np.float32) / 255.0)[..., None]
    tint = np.array([236, 72, 153], np.float32)
    out = rgb.astype(np.float32) * a + (rgb.astype(np.float32) * 0.35 + tint * 0.65) * (1 - a)
    return _b64_jpeg(np.clip(out, 0, 255).astype(np.uint8))


def _input_face_checks(face: face_analysis.FaceAnalysis, spec: dict, policy: dict) -> list[Check]:
    checks = []
    ratio = face.secondary_face_ratio
    if face.face_count > 1 and ratio >= policy["secondary_face_reject_ratio"]:
        checks.append(Check("in.single_person", "face", "Only one person in the photo", FAIL,
                            f"{face.face_count} faces found. The MFA rules do not allow another person in the photo.",
                            stage="input", remedy="retake"))
    elif face.face_count > 1:
        checks.append(Check("in.single_person", "face", "Only one person in the photo", WARN,
                            "A small second face (poster, picture or reflection) was found in the background. "
                            "It is removed with the background, but check the result.", stage="input", basis="provisional"))
    else:
        checks.append(Check("in.single_person", "face", "Only one person in the photo", PASS, "One face.", stage="input"))

    conf = face.confidence
    status = PASS if conf >= policy["review_face_confidence"] else WARN if conf >= policy["min_face_confidence"] else FAIL
    checks.append(Check("in.face_confidence", "face", "Face detection confidence", status,
                        {PASS: "Face detected clearly.",
                         WARN: "Face detection is uncertain. Review the result carefully.",
                         FAIL: "The face could not be detected reliably. Retake with the face well lit and facing the camera."}[status],
                        stage="input", basis="provisional", measured=round(conf, 2),
                        expected=f"≥ {policy['review_face_confidence']}", remedy="retake" if status == FAIL else None))

    lim, warn = spec["pose_limits"], policy["pose_warn"]
    for key, label, value, limit, soft in (
        ("yaw", "Facing the camera (left/right turn)", face.yaw_deg, lim["max_abs_yaw_deg"], warn["yaw_deg"]),
        ("pitch", "Head level (up/down)", face.pitch_deg, lim["max_abs_pitch_deg"], warn["pitch_deg"]),
    ):
        v = abs(value)
        status = FAIL if v > limit else WARN if v > soft else PASS
        msg = {PASS: f"{value:+.1f}°.",
               WARN: f"{value:+.1f}°: within the MFA limit of {limit}° but noticeably {'turned' if key == 'yaw' else 'tilted up or down'}. "
                     "This cannot be corrected by editing; a straight-on retake is safer.",
               FAIL: f"{value:+.1f}° exceeds the MFA limit of {limit}°. Retake looking straight at the camera."}[status]
        checks.append(Check(f"in.pose_{key}", "pose", label, status, msg, stage="input",
                            basis="verified" if status != WARN else "provisional",
                            measured=round(value, 1), unit="°", expected=f"≤ {limit}°",
                            remedy="retake" if status != PASS else None))

    ex, b = policy["expression"], face.blendshapes
    if b:
        blink = max(b.get("eyeBlinkLeft", 0), b.get("eyeBlinkRight", 0))
        checks.append(Check("in.eyes_open", "face", "Eyes open", FAIL if blink > ex["eye_blink_max"] else PASS,
                            "Eyes appear closed." if blink > ex["eye_blink_max"] else "Eyes open.",
                            stage="input", basis="provisional", measured=round(blink, 2),
                            expected=f"blink ≤ {ex['eye_blink_max']}", remedy="retake" if blink > ex["eye_blink_max"] else None))
        jaw = b.get("jawOpen", 0)
        checks.append(Check("in.mouth_closed", "face", "Mouth closed", FAIL if jaw > ex["jaw_open_max"] else PASS,
                            "Mouth is open." if jaw > ex["jaw_open_max"] else "Mouth closed.",
                            stage="input", basis="provisional", measured=round(jaw, 2),
                            expected=f"≤ {ex['jaw_open_max']}", remedy="retake" if jaw > ex["jaw_open_max"] else None))
        smile = (b.get("mouthSmileLeft", 0) + b.get("mouthSmileRight", 0)) / 2
        checks.append(Check("in.neutral", "face", "Neutral expression", WARN if smile > ex["smile_warn"] else PASS,
                            "You appear to be smiling. The MFA requires a neutral expression." if smile > ex["smile_warn"]
                            else "Neutral expression.", stage="input", basis="provisional", measured=round(smile, 2),
                            expected=f"smile ≤ {ex['smile_warn']}", remedy="retake" if smile > ex["smile_warn"] else None))
    return checks


def _tilt_checks(face: face_analysis.FaceAnalysis, applied_deg: float, mode: str, policy: dict, spec: dict) -> list[Check]:
    residual = face.eye_roll_deg
    limit = spec["pose_limits"]["max_abs_roll_deg"]
    warn = policy["tilt"]["head_roll_warn_deg"]
    if abs(residual) > warn:
        why = {"off": "Straightening is turned off.", "manual": "The manual angle does not level it."}.get(
            mode, "It could not be straightened automatically.")
        return [Check("in.head_tilt", "pose", "Head held straight", WARN if abs(residual) <= limit else FAIL,
                      f"Your head is tilted {residual:+.1f}°. {why} Retake with your head straight, or straighten it manually.",
                      stage="input", basis="provisional", measured=round(residual, 1), unit="°", remedy="retake")]
    return [Check("in.head_tilt", "pose", "Head held straight", PASS,
                  f"Straightened by {applied_deg:+.1f}°; eye line now {residual:+.1f}°." if applied_deg else f"Eye line {residual:+.1f}°.",
                  stage="input", basis="provisional", measured=round(residual, 1), unit="°")]


def _geometry_input_checks(plan, head, policy: dict, coverage: np.ndarray, src_alpha: np.ndarray) -> list[Check]:
    checks = []
    s = plan.scale
    if s > policy["reject_upscale"]:
        status, msg = FAIL, f"The face is too small in the original (enlarged {s:.1f}×). Retake closer to the camera."
    elif s > policy["max_upscale"]:
        status, msg = WARN, f"The face is enlarged {s:.1f}×, which softens detail. A closer or higher-resolution photo is better."
    else:
        status, msg = PASS, "Source resolution is sufficient."
    checks.append(Check("in.resolution", "geometry", "Enough resolution in the original", status, msg,
                        stage="input", basis="provisional", measured=round(s, 2), expected=f"scale ≤ {policy['max_upscale']}",
                        remedy="retake" if status != PASS else None))

    h = coverage.shape[0]
    missing_bottom = (~coverage[int(h * 0.8):]).mean()
    body_at_bottom = (src_alpha[-3:] > 127).mean() > 0.05
    if missing_bottom > 0.05 and body_at_bottom:
        checks.append(Check("in.body_cutoff", "geometry", "Shoulders fully in the original frame", WARN,
                            "The original photo is cut off too close below the chin, so the bottom of the new photo had to be filled. "
                            "Retake with more space below your shoulders.", stage="input", basis="provisional", remedy="retake"))
    if head.crown_clipped:
        checks.append(Check("in.crown_visible", "geometry", "Top of head inside the original frame", WARN,
                            "The top of the head touches the edge of the original photo, so the crown position is estimated. "
                            "Retake with space above your head.", stage="input", basis="provisional", remedy="retake"))
    if not plan.feasible:
        checks.append(Check("in.geometry_feasible", "geometry", "Layout can meet every size rule", FAIL,
                            " ".join(plan.notes) or "The required proportions could not all be met.",
                            stage="input", basis="verified", remedy="adjust"))
    return checks


def _decision(checks: list[Check]) -> tuple[str, str]:
    active = [c for c in checks if c.group != "checklist"]
    if any(c.status == FAIL and c.remedy == "retake" for c in active):
        return "retake", "This photo cannot be corrected safely. Please take a new photo."
    if any(c.status == FAIL for c in active):
        return "review", "Some requirements are not met. Adjust the photo manually or retake."
    if any(c.status == WARN for c in active):
        return "review", "The photo was processed, but please review the warnings before using it."
    return "pass", "All automatically verifiable requirements are met."


def _advice(checks: list[Check]) -> list[str]:
    tips = []
    for c in checks:
        if c.remedy == "retake" and c.status in (FAIL, WARN):
            tips.append(c.message)
    return list(dict.fromkeys(tips))


def process(image_bytes: bytes, profile: str = "digital", overrides: dict | None = None,
            alpha_png: bytes | None = None, spec_id: str = "CHINA_VISA") -> dict:
    t0 = time.time()
    timings = {}
    spec = load_spec(spec_id)
    policy = spec["policy"]
    c = constraints_for(spec, profile)
    ov = Overrides.from_dict(overrides)
    bg_rgb = hex_to_rgb(spec["background"]["color"])

    rgb0 = decode_image(image_bytes, policy["working_max_side_px"])
    working_size = (rgb0.shape[1], rgb0.shape[0])
    base = {
        "success": True,
        "spec": spec_summary(spec),
        "profile": profile,
        "original_preview": _b64_jpeg(rgb0),
        "working_size": {"width": working_size[0], "height": working_size[1]},
    }

    face0 = face_analysis.analyze_face(rgb0)
    timings["face_ms"] = round((time.time() - t0) * 1000)
    if face0 is None:
        checks = [Check("in.face", "face", "Face detected", FAIL,
                        "No face was found. Use a clear, well-lit, front-facing photo of one person.", stage="input", remedy="retake")]
        return {**base, "decision": "retake", "summary": "No face detected.", "checks": [x.as_dict() for x in checks],
                "corrections": [], "retake_advice": [checks[0].message], "processed_image": None,
                "analysis": {}, "timings": timings}

    checks = _input_face_checks(face0, spec, policy)

    t = time.time()
    if alpha_png is not None:
        alpha0 = segmentation.decode_alpha(alpha_png, working_size)
    else:
        alpha0 = segmentation.segment_person(rgb0)
        alpha0 = segmentation.keep_main_subject(alpha0, tuple(face0.landmarks[face_analysis.NOSE_TIP]))
    timings["segmentation_ms"] = round((time.time() - t) * 1000)

    # --- Tilt: camera vs head ---
    t = time.time()
    tp = policy["tilt"]
    try:
        scene = tilt.scene_line_reference(rgb0, alpha0, min_lines=tp["min_scene_lines"])
    except Exception:
        scene = None
    try:
        shoulders = tilt.shoulder_reference(rgb0)
    except Exception:
        shoulders = None
    decision = tilt.decide_tilt(face0.eye_roll_deg, face0.confidence, scene, shoulders, tp)
    if ov.rotation == "off":
        angle = 0.0
    elif ov.rotation == "manual":
        angle = ov.rotation_deg
    else:
        angle = decision.angle_deg if decision.auto_apply else 0.0

    rgb, alpha, face = rgb0, alpha0, face0
    valid = np.full(alpha0.shape, 255, np.uint8)
    rotation_note = None
    if abs(angle) >= 0.05:
        r_rgb, r_alpha, r_valid, _ = transform.rotate(rgb0, alpha0, angle, tuple(face0.eye_mid))
        r_face = face_analysis.analyze_face(r_rgb)  # re-detect; never reuse pre-rotation geometry
        if r_face is None:
            rotation_note = "Rotation was cancelled because the face could not be re-detected afterwards."
            angle = 0.0
        else:
            rgb, alpha, valid, face = r_rgb, r_alpha, r_valid, r_face
    timings["tilt_ms"] = round((time.time() - t) * 1000)
    checks += _tilt_checks(face, angle, ov.rotation, policy, spec)

    head = measure_head(face, alpha > 127, policy)

    # --- Background ---
    if ov.replace_background:
        matte_checks, matte_stats = check_matte(rgb, alpha, face, head, bg_rgb, policy)
    else:
        matte_checks, matte_stats = [check_kept_background(rgb, alpha, spec["background"])], {}
    checks += matte_checks

    # --- Lighting ---
    stats = lighting.measure(rgb, face)
    checks += lighting.lighting_checks(stats, policy, stage="input")
    if ov.lighting == "off":
        light = lighting.LightingPlan()
    elif ov.lighting == "manual":
        lp = policy["lighting"]
        light = lighting.LightingPlan(
            exposure_ev=float(np.clip(ov.exposure_ev, -lp["max_reduce_ev"], lp["max_gain_ev"])),
            contrast=float(np.clip(ov.contrast, 0.0, lp["max_contrast_strength"])),
            pivot=stats.p50 / 100.0, reasons=["Manual exposure/contrast."])
    else:
        light = lighting.plan(stats, policy)
    light_reverted = None
    if not light.is_identity:
        ok, msg = lighting.verify_skin(rgb, lighting.apply(rgb, light), face, policy)
        if not ok:
            light_reverted = msg
            light = lighting.LightingPlan()
        else:
            light.reasons.append(msg)

    # --- Geometry ---
    plan = solve(head, c, ov.crop, hair_allowance=policy["crown"]["hair_allowance"])
    head = plan.head or head

    # --- Render + encode ---
    t = time.time()
    rendered = render(rgb, alpha, valid, plan, c, bg_rgb, light, ov.replace_background, ov.edge_refine)
    data, quality, enc_notes = encode_jpeg(rendered.rgb, c.dpi, c.min_kb, c.max_kb)
    timings["render_ms"] = round((time.time() - t) * 1000)
    checks += _geometry_input_checks(plan, head, policy, rendered.coverage, alpha)

    # --- Validate the exported bytes ---
    t = time.time()
    out_checks, measured = validate_output(data, c, spec, policy, bg_rgb, rendered.alpha if ov.replace_background else None,
                                           plan.predicted)
    timings["validate_ms"] = round((time.time() - t) * 1000)
    checks += out_checks
    checks += checklist_items()

    decision_state, summary = _decision(checks)

    corrections = [
        {
            "id": "rotation",
            "label": "Straighten head tilt" if decision.classification in ("head_tilt", "ambiguous") else "Straighten camera tilt",
            "applied": abs(angle) >= 0.05,
            "mode": ov.rotation,
            "angle_deg": round(angle, 2),
            "suggested": decision.suggest and ov.rotation == "auto",
            "suggested_angle_deg": round(decision.angle_deg, 2),
            "reason": rotation_note or decision.reason,
            "confidence": round(decision.confidence, 2),
            "classification": decision.classification,
        },
        {
            "id": "background",
            "label": "Replace background with white",
            "applied": ov.replace_background,
            "edge_refine": ov.edge_refine,
            "reason": "Person segmented with BiRefNet; hair edges colour-decontaminated." if ov.replace_background
                      else "Original background kept.",
        },
        {
            "id": "lighting",
            "label": "Exposure and contrast",
            "applied": not light.is_identity,
            "mode": ov.lighting,
            **light.as_dict(),
            "reason": light_reverted or ("; ".join(light.reasons) if light.reasons else "No correction needed."),
        },
        {
            "id": "crop",
            "label": f"Crop and scale to {c.width}×{c.height} px",
            "applied": True,
            "manual": not ov.crop.is_identity,
            "scale": round(plan.scale, 4),
            "adjust": {"scale": ov.crop.scale, "offset_x": ov.crop.offset_x, "offset_y": ov.crop.offset_y},
            "reason": "; ".join(plan.notes) or f"Head scaled {plan.scale:.2f}× and positioned by the {spec['source']['edition']} rules.",
        },
    ]

    guides = {
        "crown_y": measured.get("geometry_px", {}).get("crown_to_top"),
        "eye_y": c.height - measured["geometry_px"]["eye_line_to_bottom"] if "geometry_px" in measured else None,
        "chin_y": c.height - measured["geometry_px"]["chin_to_bottom"] if "geometry_px" in measured else None,
        "crown_band": [c.crown_to_top.min, c.crown_to_top.max],
        "eye_max_y": c.height - c.eye_line_to_bottom.min if c.eye_line_to_bottom else None,
        "chin_max_y": c.height - c.chin_to_bottom.min if c.chin_to_bottom else None,
        "center_x": c.width / 2,
    }

    timings["total_ms"] = round((time.time() - t0) * 1000)
    return {
        **base,
        "decision": decision_state,
        "summary": summary,
        "processed_image": base64.b64encode(data).decode(),
        "mask_preview": _mask_preview(rgb, alpha),
        "alpha_png": base64.b64encode(segmentation.encode_alpha(alpha0)).decode(),
        "corrections": corrections,
        "checks": [x.as_dict() for x in checks],
        "retake_advice": _advice(checks),
        "guides": guides,
        "analysis": {
            "face": face0.summary(),
            "tilt": decision.as_dict(),
            "head": head.as_dict(),
            "lighting": stats.as_dict(),
            "matte": {k: round(v, 4) for k, v in matte_stats.items()},
            "plan": plan.as_dict(),
        },
        "output": {**measured, "quality": quality, "format": "JPEG", "notes": enc_notes},
        "timings": timings,
    }
