"""Turn every training image into MobileNetV2 features (run once; ~25 minutes on 2 CPU cores).

    python -m ml.extract_features --plantvillage DIR --plantdoc DIR --paddy DIR --out DIR

DIRs are the checked-out datasets:
  PlantVillage  https://github.com/spMohanty/PlantVillage-Dataset   (use raw/color)
  PlantDoc      https://github.com/pratikkayal/PlantDoc-Dataset
  Paddy Doctor  https://github.com/ai-agriculture-circuits-and-systems/paddy_disease_classification

Each image becomes several "views": the standard centre crop, its mirror image, and (for
training images only) a few random crops, so the classifier learns that a leaf can sit
anywhere in the frame at different zoom levels.
"""
import argparse
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from agri.vision import FeatureExtractor, flipped_view, load_image, random_crop_view, standard_view
from ml.disease_labels import CLASS_INDEX, PADDY, PLANTDOC, PLANTVILLAGE

IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def bucket(path: str) -> float:
    """Stable pseudo-random number in [0, 1) from a file name, so splits never change."""
    return int(hashlib.md5(path.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def build_manifest(pv: Path | None, pd: Path | None, paddy: Path | None):
    rows = []  # (path, class id, source, split)
    if pv:
        root = pv / "raw" / "color"
        for folder, cls in PLANTVILLAGE.items():
            for p in sorted((root / folder).iterdir()):
                if p.suffix.lower() in IMG_EXT:
                    b = bucket(p.name)
                    split = "test" if b < 0.10 else "val" if b < 0.20 else "train"
                    rows.append((str(p), cls, "plantvillage", split))
    if pd:
        for part in ("train", "test"):
            for folder, cls in PLANTDOC.items():
                d = pd / part / folder
                if not d.exists():
                    continue
                for p in sorted(d.iterdir()):
                    if p.suffix.lower() in IMG_EXT:
                        split = "test" if part == "test" else ("val" if bucket(p.name) < 0.15 else "train")
                        rows.append((str(p), cls, "plantdoc", split))
    if paddy:
        for folder, cls in PADDY.items():
            base = paddy / "paddies" / folder
            for part in ("train", "val", "test"):
                for stem in (base / "sets" / f"{part}.txt").read_text().split():
                    p = base / "images" / f"{stem}.jpg"
                    if p.exists():
                        rows.append((str(p), cls, "paddy", part))
    return rows


def views_for(source: str, split: str) -> list[str]:
    if split != "train":
        return ["std", "flip"]
    extra = 2 if source == "plantvillage" else 4
    return ["std", "flip"] + [f"rand{i}" for i in range(extra)]


def make_views(path: str, names: list[str]):
    try:
        img = load_image(path)
    except Exception as exc:  # unreadable file: skip it
        return None, str(exc)
    rng = np.random.default_rng(int(hashlib.md5(path.encode()).hexdigest()[:8], 16))
    out = []
    for n in names:
        if n == "std":
            out.append(standard_view(img))
        elif n == "flip":
            out.append(flipped_view(img))
        else:
            out.append(random_crop_view(img, rng))
    return out, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plantvillage", type=Path)
    ap.add_argument("--plantdoc", type=Path)
    ap.add_argument("--paddy", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    manifest = build_manifest(args.plantvillage, args.plantdoc, args.paddy)
    print(f"{len(manifest)} images", flush=True)
    fx = FeatureExtractor(threads=2)

    groups = {}
    for row in manifest:
        groups.setdefault((row[2], row[3]), []).append(row)

    skipped = []
    order = sorted(groups, key=lambda k: ({"plantdoc": 0, "paddy": 1, "plantvillage": 2}[k[0]], k[1]))
    for source, split in order:
        rows = groups[(source, split)]
        names = views_for(source, split)
        dest = args.out / f"{source}_{split}.npz"
        if dest.exists():
            print(f"skip {dest.name} (exists)", flush=True)
            continue
        t0 = time.time()
        feats, labels, img_ids, view_ids, paths = [], [], [], [], []
        with ThreadPoolExecutor(max_workers=2) as pool:
            for start in range(0, len(rows), 24):
                chunk = rows[start:start + 24]
                results = list(pool.map(lambda r: make_views(r[0], names), chunk))
                batch, meta = [], []
                for j, (r, (vs, err)) in enumerate(zip(chunk, results)):
                    if vs is None:
                        skipped.append((r[0], err))
                        continue
                    for vi, v in enumerate(vs):
                        batch.append(v)
                        meta.append((start + j, vi, r))
                if not batch:
                    continue
                f = fx(np.stack(batch))
                feats.append(f.astype(np.float16))
                for (img_i, vi, r) in meta:
                    labels.append(CLASS_INDEX[r[1]])
                    img_ids.append(img_i)
                    view_ids.append(vi)
                    paths.append(r[0])
                if (start // 24) % 100 == 0:
                    done = start + len(chunk)
                    print(f"  {source}/{split}: {done}/{len(rows)} images, {done / (time.time() - t0 + 1e-9):.0f} img/s", flush=True)
        np.savez(dest, X=np.concatenate(feats), y=np.array(labels, dtype=np.int16),
                 image=np.array(img_ids, dtype=np.int32), view=np.array(view_ids, dtype=np.int8),
                 views=np.array(names), paths=np.array(paths))
        print(f"wrote {dest.name}: {len(rows)} images x {len(names)} views in {time.time() - t0:.0f}s", flush=True)

    (args.out / "skipped.json").write_text(json.dumps(skipped, indent=1))
    print(f"done, {len(skipped)} unreadable images skipped", flush=True)


if __name__ == "__main__":
    main()
