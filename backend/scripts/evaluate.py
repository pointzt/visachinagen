"""Evaluate the China visa engine on a face set and report metrics per subgroup.

    PHOTOGEN_TEST_FACES=~/photogen-faces python scripts/evaluate.py [--out report.json]

Experiments:
  * baseline      – every photo as-is: decisions, check outcomes, exported geometry
  * camera_roll   – each photo rolled ±3°/±7° (rotate + centre crop): tilt classification,
                    auto/suggested rotation, residual roll; and the false auto-rotation rate
                    on unrotated photos (the most important safety number)
  * underexposure – each photo darkened by 1 EV: whether a bounded lift is applied and
                    whether skin hue is preserved

Subgroups come from the manifest tags (glasses, hair, background, framing) and from the
measured lightness of cheek/forehead skin, split into terciles of the set. That measure mixes
skin tone with lighting (studio flash lifts everyone), so it is a relative grouping, not a
skin-type label; ITA is recorded per image for reference. No one is labelled by hand.
"""

import argparse
import collections
import io
import json
import math
import os
import sys

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.pipeline import face_analysis, lighting  # noqa: E402
from app.pipeline.cache import ensure_matte  # noqa: E402
from app.pipeline.color import rgb_to_lab, srgb_to_linear, linear_to_srgb  # noqa: E402
from app.pipeline.engine import process  # noqa: E402

def skin_colour(rgb: np.ndarray) -> tuple[float, float]:
    """(median skin L*, ITA degrees) from the forehead and cheek patches."""
    face = face_analysis.analyze_face(rgb)
    mask = lighting.skin_mask(rgb.shape[:2], face)
    lab = np.median(rgb_to_lab(rgb)[mask], axis=0)
    return float(lab[0]), math.degrees(math.atan2(lab[0] - 50, lab[2]))


def png(rgb):
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="PNG")
    return buf.getvalue()


def roll(img, angle, interp):
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), -angle, 1.0)
    out = cv2.warpAffine(img, m, (w, h), flags=interp, borderMode=cv2.BORDER_REPLICATE)
    k = int(0.1 * min(w, h))
    return out[k:h - k, k:w - k]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--faces", default=os.environ.get("PHOTOGEN_TEST_FACES"))
    ap.add_argument("--out", default="evaluation_report.json")
    ap.add_argument("--skip-roll", action="store_true")
    args = ap.parse_args()
    faces_dir = os.path.expanduser(args.faces)
    with open(os.path.join(faces_dir, "manifest.json")) as f:
        manifest = json.load(f)

    rows = []
    for entry in manifest:
        path = os.path.join(faces_dir, entry["file"])
        with open(path, "rb") as f:
            image = f.read()
        matte = ensure_matte(path)
        rgb = np.array(Image.open(io.BytesIO(image)).convert("RGB"))
        alpha = np.array(Image.open(io.BytesIO(matte)))
        skin_l, ita = skin_colour(rgb)
        row = {"id": entry["id"], "tags": dict(entry.get("tags", {})), "skin_l": round(skin_l, 1), "ita": round(ita, 1)}

        r = process(image, "digital", None, matte)
        row["decision"] = r["decision"]
        row["eye_roll"] = r["analysis"]["face"]["eye_roll_deg"]
        row["issues"] = sorted(c["id"] for c in r["checks"] if c["status"] in ("warn", "fail"))
        row["fails"] = sorted(c["id"] for c in r["checks"] if c["status"] == "fail")
        row["geometry"] = r["output"].get("geometry_px")
        row["light_applied"] = next(c for c in r["corrections"] if c["id"] == "lighting")["applied"]
        row["auto_rotated"] = next(c for c in r["corrections"] if c["id"] == "rotation")["applied"]

        # Underexposure: darken the whole frame by 1 EV in linear light.
        dark = (linear_to_srgb(srgb_to_linear(rgb / 255.0) * 0.5) * 255).astype(np.uint8)
        rd = process(png(dark), "digital", None, matte)
        lc = next(c for c in rd["corrections"] if c["id"] == "lighting")
        row["underexposed"] = {"applied": lc["applied"], "ev": lc["exposure_ev"], "reason": lc["reason"]}

        if not args.skip_roll:
            row["roll"] = {}
            for ang in (-7, -3, 3, 7):
                rr = process(png(roll(rgb, ang, cv2.INTER_CUBIC)), "digital", None, png(roll(alpha, ang, cv2.INTER_LINEAR)))
                rc = next(c for c in rr["corrections"] if c["id"] == "rotation")
                row["roll"][str(ang)] = {"classification": rc["classification"], "applied": rc["applied"],
                                         "suggested": rc["suggested"], "angle": rc["angle_deg"],
                                         "suggested_angle": rc["suggested_angle_deg"]}
        rows.append(row)
        print(entry["id"], row["skin_l"], row["decision"], row["fails"])

    cuts = np.percentile([r["skin_l"] for r in rows], [33.3, 66.7])
    for r in rows:
        r["tags"]["skin_lightness_tercile"] = ["lower", "middle", "upper"][int(np.searchsorted(cuts, r["skin_l"]))]
    summary = summarise(rows)
    with open(args.out, "w") as f:
        json.dump({"summary": summary, "rows": rows}, f, indent=1)
    print(json.dumps(summary, indent=1))


def summarise(rows):
    def stats(group):
        n = len(group)
        dec = collections.Counter(r["decision"] for r in group)
        fails = collections.Counter(f for r in group for f in r["fails"])
        under = [r["underexposed"] for r in group]
        out = {
            "n": n,
            "decisions": dict(dec),
            "fail_rate": round(sum(1 for r in group if r["fails"]) / n, 3),
            "top_fails": fails.most_common(5),
            "false_auto_rotation_on_originals": sum(r["auto_rotated"] for r in group),
            "lighting_changed_on_originals": sum(r["light_applied"] for r in group),
            "underexposure_lift_rate": round(sum(u["applied"] for u in under) / n, 3),
        }
        # Expected correction = the person's own eye roll plus the simulated camera roll.
        rolled = [v | {"true": int(k) + r["eye_roll"]} for r in group for k, v in r.get("roll", {}).items()]
        if rolled:
            handled = [x for x in rolled if x["applied"] or x["suggested"]]
            err = [abs(x["suggested_angle"] - x["true"]) for x in handled]
            out["camera_roll"] = {
                "cases": len(rolled),
                "auto_rotated": sum(x["applied"] for x in rolled),
                "offered_or_applied": len(handled),
                "classified_head_tilt": sum(x["classification"] == "head_tilt" for x in rolled),
                "median_abs_angle_error_deg": round(float(np.median(err)), 2) if err else None,
            }
        return out

    summary = {"overall": stats(rows)}
    keys = sorted({k for r in rows for k in r["tags"]})
    for key in keys:
        groups = collections.defaultdict(list)
        for r in rows:
            groups[str(r["tags"].get(key))].append(r)
        summary[key] = {g: stats(v) for g, v in sorted(groups.items())}
    return summary


if __name__ == "__main__":
    main()
