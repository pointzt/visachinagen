"""Download the development face set listed in tests/data/face_set.json.

The images are public-domain US federal official portraits hosted on Wikimedia Commons. They
are downloaded to a local folder (never committed) and optionally segmented once so the model
tests and the evaluation script do not re-run BiRefNet every time.

    python scripts/fetch_test_faces.py ~/photogen-faces [--mattes]
    export PHOTOGEN_TEST_FACES=~/photogen-faces
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

UA = {"User-Agent": "PhotoGenTestFetcher/0.1 (https://github.com/deidaraiorek/photogen; test set)"}
API = "https://commons.wikimedia.org/w/api.php?"


def fetch(url: str) -> bytes:
    for attempt in range(6):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read()
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            raise
    raise RuntimeError(f"Rate limited: {url}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("--width", type=int, default=1000)
    ap.add_argument("--mattes", action="store_true", help="also compute and cache person mattes (slow)")
    args = ap.parse_args()
    out = os.path.expanduser(args.out_dir)
    os.makedirs(out, exist_ok=True)

    with open(os.path.join(os.path.dirname(HERE), "tests", "data", "face_set.json")) as f:
        face_set = json.load(f)

    manifest = []
    for entry in face_set["faces"]:
        path = os.path.join(out, f"{entry['id']}.jpg")
        if not os.path.exists(path):
            q = {"action": "query", "titles": entry["title"], "prop": "imageinfo", "iiprop": "url|extmetadata",
                 "iiurlwidth": str(args.width), "format": "json"}
            page = next(iter(json.loads(fetch(API + urllib.parse.urlencode(q)))["query"]["pages"].values()))
            info = page["imageinfo"][0]
            lic = info["extmetadata"].get("LicenseShortName", {}).get("value", "")
            if "public domain" not in lic.lower():
                print(f"skip {entry['id']}: licence is now '{lic}'")
                continue
            with open(path, "wb") as f:
                f.write(fetch(info["thumburl"]))
            time.sleep(1.5)
        manifest.append({**entry, "file": os.path.basename(path)})
        print("ok", entry["id"])

    with open(os.path.join(out, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)

    if args.mattes:
        from app.pipeline.cache import ensure_matte
        for entry in manifest:
            ensure_matte(os.path.join(out, entry["file"]))
            print("matte", entry["id"])


if __name__ == "__main__":
    main()
