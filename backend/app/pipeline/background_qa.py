"""Quality checks for the person matte and the replaced background."""

import cv2
import numpy as np

from app.pipeline.checks import FAIL, PASS, WARN, Check
from app.pipeline.color import delta_e, lab_of, rgb_to_lab
from app.pipeline.face_analysis import FaceAnalysis
from app.pipeline.head_measure import HeadMeasure


def face_polygon_mask(shape: tuple[int, int], face: FaceAnalysis, shrink: float = 0.04) -> np.ndarray:
    mask = np.zeros(shape, np.uint8)
    cv2.fillPoly(mask, [np.round(face.oval).astype(np.int32)], 1)
    k = max(1, int(face.face_width * shrink))
    return cv2.erode(mask, np.ones((2 * k + 1, 2 * k + 1), np.uint8)).astype(bool)


def enclosed_holes(fg: np.ndarray) -> np.ndarray:
    """Background pixels fully enclosed by foreground."""
    inv = (~fg).astype(np.uint8)
    h, w = inv.shape
    flood = inv.copy()
    ff_mask = np.zeros((h + 2, w + 2), np.uint8)
    for x, y in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        if flood[y, x]:
            cv2.floodFill(flood, ff_mask, (x, y), 0)
    # Anything still 1 was not reachable from a corner; also clear border-connected regions.
    n, labels, stats, _ = cv2.connectedComponentsWithStats(flood, connectivity=4)
    holes = np.zeros_like(fg)
    for i in range(1, n):
        x, y, bw, bh, _ = stats[i]
        if x > 0 and y > 0 and x + bw < w and y + bh < h:
            holes |= labels == i
    return holes


def check_matte(rgb: np.ndarray, alpha: np.ndarray, face: FaceAnalysis, head: HeadMeasure,
                target_rgb: tuple[int, int, int], policy: dict) -> tuple[list[Check], dict]:
    q = policy["background_qa"]
    h, w = alpha.shape
    a = alpha.astype(np.float32) / 255.0
    fg = a > 0.5
    checks: list[Check] = []
    stats: dict = {}

    face_mask = face_polygon_mask(alpha.shape, face)
    coverage = float(a[face_mask].mean()) if face_mask.any() else 0.0
    stats["face_alpha"] = coverage
    checks.append(Check(
        "bg.face_coverage", "background", "Face kept intact by background removal",
        PASS if coverage >= q["face_min_alpha"] else FAIL,
        "Face fully preserved." if coverage >= q["face_min_alpha"]
        else "Background removal cut into the face. Retake against a plain background that contrasts with your skin and hair.",
        stage="input", basis="provisional", measured=coverage, expected=f"≥ {q['face_min_alpha']}",
        remedy=None if coverage >= q["face_min_alpha"] else "retake",
    ))

    # Holes inside the head region (hair and face).
    y0 = max(0, int(head.crown_y))
    y1 = min(h, int(head.chin_y + 0.05 * head.head_height))
    x0 = max(0, int(head.center_x - 0.65 * head.face_width))
    x1 = min(w, int(head.center_x + 0.65 * head.face_width))
    holes = enclosed_holes(fg)
    region = np.zeros_like(fg)
    region[y0:y1, x0:x1] = True
    head_area = max(1, int((fg & region).sum()))
    # Holes on or right next to the face are segmentation errors; gaps between curls or strands
    # of hair are usually real background showing through, so they only warn when large.
    k = max(3, int(0.08 * face.face_width))
    face_zone = cv2.dilate(face_polygon_mask(alpha.shape, face, shrink=0.0).astype(np.uint8),
                           np.ones((2 * k + 1, 2 * k + 1), np.uint8)).astype(bool)
    face_hole = float((holes & face_zone).sum()) / head_area
    hair_zone = region & ~face_zone
    hair_hole = float((holes & hair_zone).sum()) / max(1, int(((fg | holes) & hair_zone).sum()))
    stats["face_hole_fraction"] = face_hole
    stats["hair_hole_fraction"] = hair_hole
    if face_hole > q["head_hole_fail_fraction"]:
        status, msg, remedy = FAIL, "Parts of the face were treated as background.", "retake"
    elif hair_hole > q["hair_hole_warn_fraction"]:
        status, msg, remedy = WARN, ("Gaps in the hair show the background. This is often natural for curly or "
                                     "loose hair; check the hair outline in the mask preview."), None
    else:
        status, msg, remedy = PASS, "Head outline is solid.", None
    checks.append(Check(
        "bg.head_holes", "background", "No holes in the head outline", status, msg,
        stage="input", basis="provisional", measured=f"face {face_hole:.4f}, hair {hair_hole:.4f}",
        expected=f"face ≤ {q['head_hole_fail_fraction']}, hair ≤ {q['hair_hole_warn_fraction']}", remedy=remedy,
    ))

    lab = rgb_to_lab(rgb)
    target_lab = lab_of(target_rgb)

    # Garment identical to background (explicit MFA rejection example).
    gy0 = min(h, int(head.chin_y + 0.25 * head.head_height))
    gy1 = min(h, int(head.chin_y + 0.8 * head.head_height))
    gx0 = max(0, int(head.center_x - 1.2 * head.face_width))
    gx1 = min(w, int(head.center_x + 1.2 * head.face_width))
    garment = fg[gy0:gy1, gx0:gx1]
    if garment.sum() > 200:
        g_lab = np.median(lab[gy0:gy1, gx0:gx1][garment], axis=0)
        g_de = float(delta_e(g_lab, target_lab))
        stats["garment_delta_e"] = g_de
        similar = g_de < q["garment_similarity_delta_e"]
        checks.append(Check(
            "bg.garment_contrast", "background", "Clothing differs from background",
            WARN if similar else PASS,
            "Clothing is very close to the background colour (MFA rejects garments identical to the background). Wear darker or coloured clothing."
            if similar else "Clothing contrasts with the background.",
            stage="input", basis="provisional", measured=g_de, expected=f"ΔE ≥ {q['garment_similarity_delta_e']}",
            remedy="retake" if similar else None,
        ))

    # Shadow of the person kept inside the cutout: foreground near the contour whose colour
    # matches a darkened version of the original background.
    bg_px = a < 0.04
    if bg_px.sum() > 500:
        bg_lab = np.median(lab[bg_px], axis=0)
        k = max(3, int(0.02 * np.hypot(w, h)))
        inner = fg & ~cv2.erode(fg.astype(np.uint8), np.ones((k, k), np.uint8)).astype(bool)
        inner[: int(head.crown_y)] = False
        if inner.sum() > 200:
            chroma_d = np.linalg.norm(lab[..., 1:][inner] - bg_lab[1:], axis=-1)
            dl = bg_lab[0] - lab[..., 0][inner]
            shadow_like = (chroma_d < 6) & (dl > 4) & (dl < 45)
            frac = float(shadow_like.mean())
            stats["shadow_like_fraction"] = frac
            checks.append(Check(
                "bg.shadow_edges", "background", "No background shadow kept around the person",
                WARN if frac > 0.25 else PASS,
                "Edges of the cutout look like a shadow on the original background. Check the outline in the mask preview."
                if frac > 0.25 else "No shadow detected along the outline.",
                stage="input", basis="provisional", measured=frac, expected="≤ 0.25",
            ))
    return checks, stats


def check_kept_background(rgb: np.ndarray, alpha: np.ndarray, spec_bg: dict) -> Check:
    """When replacement is turned off, the original background must already be white-ish."""
    lab = rgb_to_lab(rgb)
    bg = alpha < 10
    if bg.sum() < 100:
        return Check("bg.kept_white", "background", "Original background is white", WARN,
                     "Too little background visible to evaluate.", stage="input", basis="provisional")
    med = np.median(lab[bg], axis=0)
    chroma = float(np.hypot(med[1], med[2]))
    ok = med[0] >= spec_bg["min_lightness_when_kept"]["value"] and chroma <= spec_bg["max_chroma_when_kept"]["value"]
    return Check("bg.kept_white", "background", "Original background is white", PASS if ok else FAIL,
                 "Original background is white or near white." if ok
                 else "The original background is not white. Turn background replacement back on.",
                 stage="input", basis="provisional", measured=f"L*={med[0]:.0f}, C*={chroma:.0f}",
                 expected="L* ≥ 90, C* ≤ 8", remedy=None if ok else "adjust")


def check_output_background(rgb: np.ndarray, fg: np.ndarray, target_rgb: tuple[int, int, int],
                            spec_bg: dict, render_alpha: np.ndarray | None, policy: dict) -> list[Check]:
    q = policy["background_qa"]
    h, w = fg.shape
    lab = rgb_to_lab(rgb)
    target = lab_of(target_rgb)
    band = max(3, int(0.04 * w))
    border = np.zeros_like(fg)
    border[:band] = border[-band:] = True
    border[:, :band] = border[:, -band:] = True
    sample = border & ~fg
    if render_alpha is not None:
        # Light clothing can be close to white; the render matte says what is really subject.
        ra = render_alpha.astype(np.float32) / 255.0 if render_alpha.dtype == np.uint8 else render_alpha
        sample &= cv2.dilate((ra > 0.02).astype(np.uint8), np.ones((5, 5), np.uint8)) == 0
    checks = []
    if sample.sum() > 50:
        de = delta_e(lab[sample], target)
        mean_de, std_de = float(de.mean()), float(de.std())
        max_mean = spec_bg["max_mean_delta_e"]["value"]
        max_std = spec_bg["max_std_delta_e"]["value"]
        ok = mean_de <= max_mean and std_de <= max_std
        checks.append(Check(
            "out.background_color", "background", "Background is white and uniform",
            PASS if ok else FAIL,
            "Background is uniform white." if ok else "Background is not uniformly white.",
            basis="verified", measured=f"ΔE mean {mean_de:.1f}, σ {std_de:.1f}",
            expected=f"ΔE mean ≤ {max_mean}, σ ≤ {max_std} (provisional tolerance)", remedy=None if ok else "adjust",
        ))
    # Borders: every outer 2 px edge must be background wherever the person does not touch it.
    # Pixels next to the subject (e.g. a white collar at the bottom edge) are not border candidates,
    # and an edge the subject mostly covers cannot carry a border.
    near = cv2.dilate(fg.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
    edge_bad = False
    for sl in (np.s_[:2], np.s_[-2:], np.s_[:, :2], np.s_[:, -2:]):
        s = ~near[sl]
        if s.sum() > 0.25 * s.size and float(delta_e(lab[sl][s], target).mean()) > q["output_edge_delta_e"]:
            edge_bad = True
    checks.append(Check(
        "out.no_border", "background", "No border around the image", FAIL if edge_bad else PASS,
        "A border or edge line is visible." if edge_bad else "No border.", basis="verified",
        remedy="adjust" if edge_bad else None,
    ))

    if render_alpha is not None:
        a = render_alpha.astype(np.float32) / 255.0 if render_alpha.dtype == np.uint8 else render_alpha
        subject = (a > 0.5).astype(np.uint8)
        ring = cv2.dilate(subject, np.ones((5, 5), np.uint8)).astype(bool) & (a < 0.15)
        if ring.sum() > 50:
            de = delta_e(lab[ring], target)
            frac = float((de > q["halo_delta_e"]).mean())
            checks.append(Check(
                "out.halo", "background", "No halo around hair and shoulders",
                WARN if frac > q["halo_warn_fraction"] else PASS,
                "A visible fringe remains around the outline. Try the mask preview and edge refinement."
                if frac > q["halo_warn_fraction"] else "Edges blend cleanly into the background.",
                basis="provisional", measured=frac, expected=f"≤ {q['halo_warn_fraction']}",
            ))
    return checks
