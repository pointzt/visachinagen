# China visa photo engine (API v2)

A processing and validation pipeline for Chinese visa photos, built to the MFA Department of
Consular Affairs sheet *Photo Requirements for Chinese Visa Application* (2016). It runs next to
the original `/api/process` flow, which is unchanged.

The UI is the **China visa (MFA 2016 checks)** tab on the home page
(`frontend/src/components/china/`). The API is `POST /api/v2/process`.

## Pipeline

```
decode + EXIF orientation (max 2000 px working copy)
  → face landmarks, yaw/pitch/roll, expression        face_analysis.py  (MediaPipe Face Landmarker)
  → person matte on the original pixels               segmentation.py   (BiRefNet-portrait via rembg)
  → camera tilt vs head tilt                          tilt.py           (background lines, shoulders)
  → rigid rotation of image + matte, then RE-DETECT   transform.py
  → crown / chin / eyes / face width                  head_measure.py
  → matte QA (face holes, hair gaps, garment, shadow) background_qa.py
  → exposure / contrast plan (global, bounded)        lighting.py
  → crop solver against the spec                      geometry.py
  → matte refinement, composite, JPEG 40–120 KB       render.py
  → re-decode the JPEG and re-measure everything      output_validator.py
```

`engine.py` orchestrates the stages and returns a report:

- `decision`: `pass`, `review` or `retake`.
- `corrections[]`: every automatic change, with its reason and confidence. Each can be undone
  through `overrides`.
- `checks[]`: each check has `stage` (`input`/`output`) and `basis`. `verified` means the MFA
  sheet states the number. `provisional` means a PhotoGen threshold for a rule the sheet states
  only qualitatively.
- `retake_advice[]`, measurement `guides`, `mask_preview`, and `alpha_png`.

Send `alpha_png` back as `alpha` to re-render with new overrides without re-segmenting. That
takes ~0.2 s instead of ~20 s on CPU. The server stays stateless and stores no images.

## Specification

`shared/specs/china_visa.v1.json` is versioned and records its source. Digital measurements
in the sheet are given "with the 354×472 photo as an example", so they are scaled to the
output size.

| Rule | Digital (420×560 output) | Paper (33×48 mm, 390×567 px @300 dpi) |
|---|---|---|
| Size | 354×472 – 420×560 px, JPEG, 40–120 KB | 33×48 mm |
| Crown to top edge | 10–70 px @354×472 | 3–5 mm |
| Eye line to bottom edge | > 256 px @354×472 | — |
| Face / head width | 205 ± 14 px @354×472 ¹ | 15–22 mm |
| Head height (chin–crown) | — | 28–33 mm |
| Chin to bottom edge | ≥ 4 % (provisional) | ≥ 7 mm |
| Inter-eye distance | > 60 px @354×472 | — |
| Pose | yaw, roll ≤ 20°; pitch ≤ 25° | same |
| Background | white or near white, no border | same |

¹ The body text says 205 ± 14 px, but the diagram label reads 191–251 px. The body text is used.

The sheet allows voluminous hair to be trimmed at the top edge. The solver therefore retries
with a trimmed-hair crown when the hair-inclusive layout is infeasible, and the output
validator reports that case as `provisional`.

The legacy `CHINA_VISA` entry in `shared/photo_requirements.json` (390×567, ≤120 KB) mixes the
paper size with the digital file limit, and 567 px exceeds the 560 px digital maximum. It is
left untouched for the v1 flow. Use the v2 tab for China visas.

## Safety rules

- **Rotation** is automatic only when straight background lines agree with the eye line
  (within 2°, |angle| ≤ 10°, face confidence ≥ 0.85).
  - Shoulder agreement alone, or no reference at all, gives a *suggested* one-click rotation.
  - Level references with a tilted eye line mean head tilt. The photo is not rotated, and a
    retake is advised.
  - Rotation is rigid. Faces are never warped.
- **Lighting** uses global, chroma-preserving operations only. Exposure is lifted (≤ +0.5 EV)
  only when the face's highlights are dark *and* nothing in the frame is bright, so a
  correctly exposed dark-skinned subject is never lightened. Exposure is never reduced
  automatically. Contrast is added only for hazy faces (lifted blacks). A change is reverted
  if skin hue shifts > 3° or saturation changes > 10 %. Side shadows, blow-outs and colour
  casts are reported, not fixed.
- No generative model touches the image.

## Tests and evaluation

```bash
cd backend
pip install -r requirements.txt -r requirements-dev.txt
pytest                                         # 83 model-free tests (synthetic faces, masks, geometry)
python scripts/fetch_test_faces.py ~/photogen-faces --mattes
PHOTOGEN_TEST_FACES=~/photogen-faces pytest    # + model tests on real faces
PHOTOGEN_TEST_FACES=~/photogen-faces python scripts/evaluate.py --out report.json
```

The development set is 40 public-domain US federal official portraits
(`backend/tests/data/face_set.json`; images are downloaded, not committed). It includes glasses,
curly, braided and voluminous hair, bald heads, a range of skin tones, and plain or busy
backgrounds. Results at spec v1.0.0:

| Metric | Result |
|---|---|
| Hard failures on originals | 0 / 40 (all `review`: 34 subjects smile, 15 sources are low-resolution) |
| False automatic rotation on originals | 0 / 40 |
| Lighting changed on correctly exposed originals | 0 / 40 |
| −1 EV underexposed copies lifted | 40 / 40 |
| Simulated camera roll ±3°/±7°: rotation offered or applied | 141 / 160 (auto: 0, see limitations) |
| Suggested angle error (median) | 0.22° |

The same metrics are broken down in the report by glasses, hair type, background type and
skin-lightness tercile. They are consistent across groups on this set.

## Limitations

- **Camera tilt vs head tilt** can often not be decided from one photo. Plain walls and blurred
  backdrops have no straight lines, and shoulders are rarely level. Most tilted photos therefore
  get a *suggested* rotation rather than an automatic one. This is intentional.
- **Crown under hair** is estimated. For voluminous hair, the anatomical crown comes from the
  chin-to-forehead distance (ratio 1.28, from bald subjects in the calibration set) and is
  treated as provisional.
- **The test set is studio portraits.** It is well lit, mostly smiling, and has few
  phone-selfie conditions. It is not a substitute for a consented, representative capture set
  with ground-truth crown and chin annotations. Skin-lightness groups are photo-measured, so
  they mix skin tone and lighting.
- **Not detected:** tinted lenses, glare, red-eye, head coverings and jewellery. These are
  listed as "please confirm" items.
- **Lighting edge case:** a very dark scene with no bright element at all can still receive the
  capped +0.5 EV lift. The lift is shown in the corrections list and can be undone.
- **Speed:** BiRefNet takes ~20 s per photo on CPU. Only the first request pays this cost.
- **Deployment:** the Docker build context is `backend/`, so `shared/specs/` must be copied in
  the same way as `shared/photo_requirements.json`, or `PHOTOGEN_SPECS_DIR` must be set.
- Passing the checks does not guarantee acceptance by a consulate.
