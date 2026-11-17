"""Train the leaf-disease classifier on top of the frozen MobileNetV2 features.

    python -m ml.train_disease --features DIR      (DIR = output of ml.extract_features)

Training images
  PlantVillage  54,305 lab photos, one leaf on a plain background, 38 classes of 14 crops
  PlantDoc       2,578 photos taken in real fields and gardens, 28 of the same classes
  Paddy Doctor  10,407 field photos of rice from Tamil Nadu, 10 classes

Why three sets: a model trained only on PlantVillage looks excellent on PlantVillage and
then fails on a phone photo taken in a field. So field photos are mixed into training, and
accuracy is reported separately for lab photos and for field photos the model never saw.

The classifier is a small neural network (1280 -> 512 -> 48) trained with plain numpy and
saved as arrays in models/disease_head.npz, so the app needs no deep-learning library.
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np

from ml.disease_labels import CLASSES

BACKEND = Path(__file__).resolve().parent.parent
SOURCES = ["plantvillage", "plantdoc", "paddy"]
N_CLASSES = len(CLASSES)
CROP_OF = [c.split("_")[0] for c in CLASSES]  # "tomato_late_blight" -> "tomato"
CROPS = sorted(set(CROP_OF))
CROP_MASK = np.array([[CROP_OF[j] == crop for j in range(N_CLASSES)] for crop in CROPS])


def load(features: Path, source: str, split: str):
    z = np.load(features / f"{source}_{split}.npz", allow_pickle=False)
    return z["X"], z["y"].astype(np.int64), z["image"], z["view"]


def softmax(z):
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


class Head:
    def __init__(self, hidden: int, mean, std, seed=7):
        rng = np.random.default_rng(seed)
        self.mean, self.std = mean.astype(np.float32), std.astype(np.float32)
        self.hidden = hidden
        if hidden:
            self.W1 = (rng.standard_normal((1280, hidden)) * np.sqrt(2 / 1280)).astype(np.float32)
            self.b1 = np.zeros(hidden, np.float32)
            self.W2 = (rng.standard_normal((hidden, N_CLASSES)) * np.sqrt(1 / hidden)).astype(np.float32)
        else:
            self.W2 = np.zeros((1280, N_CLASSES), np.float32)
        self.b2 = np.zeros(N_CLASSES, np.float32)
        self.T = 1.0

    def params(self):
        return [self.W1, self.b1, self.W2, self.b2] if self.hidden else [self.W2, self.b2]

    def logits(self, X, batch=4096):
        out = []
        for i in range(0, len(X), batch):
            x = (X[i:i + batch].astype(np.float32) - self.mean) / self.std
            if self.hidden:
                x = np.maximum(x @ self.W1 + self.b1, 0)
            out.append(x @ self.W2 + self.b2)
        return np.concatenate(out)

    def fit(self, X, y, sample_p, val, epochs=30, batch=512, lr=1e-3, wd=1e-4, drop=0.3, smooth=0.1, seed=7):
        rng = np.random.default_rng(seed)
        ps = self.params()
        m = [np.zeros_like(p) for p in ps]
        v = [np.zeros_like(p) for p in ps]
        steps_per_epoch = len(X) // batch
        total, step, best, best_state = epochs * steps_per_epoch, 0, -1.0, None
        for epoch in range(epochs):
            t0 = time.time()
            order = rng.choice(len(X), size=steps_per_epoch * batch, p=sample_p)
            for s in range(steps_per_epoch):
                idx = np.sort(order[s * batch:(s + 1) * batch])
                x = (X[idx].astype(np.float32) - self.mean) / self.std
                x += rng.standard_normal(x.shape).astype(np.float32) * 0.1  # small feature noise
                target = np.full((batch, N_CLASSES), smooth / N_CLASSES, np.float32)
                target[np.arange(batch), y[idx]] += 1 - smooth
                if self.hidden:
                    h = np.maximum(x @ self.W1 + self.b1, 0)
                    keep = (rng.random(h.shape) > drop).astype(np.float32) / (1 - drop)
                    hd = h * keep
                    d = (softmax(hd @ self.W2 + self.b2) - target) / batch
                    gW2, gb2 = hd.T @ d, d.sum(0)
                    dh = (d @ self.W2.T) * keep * (h > 0)
                    grads = [x.T @ dh, dh.sum(0), gW2, gb2]
                else:
                    d = (softmax(x @ self.W2 + self.b2) - target) / batch
                    grads = [x.T @ d, d.sum(0)]
                step += 1
                rate = lr * 0.5 * (1 + np.cos(np.pi * step / total))  # cosine decay
                for p, g, mi, vi in zip(ps, grads, m, v):
                    if p.ndim == 2:
                        g = g + wd * p
                    mi[:] = 0.9 * mi + 0.1 * g
                    vi[:] = 0.999 * vi + 0.001 * g * g
                    p -= rate * (mi / (1 - 0.9 ** step)) / (np.sqrt(vi / (1 - 0.999 ** step)) + 1e-8)
            score = float(np.mean([top_k(self, *val[s])[0] for s in val]))  # mean over sources
            if score > best:
                best, best_state = score, [p.copy() for p in ps]
            print(f"    epoch {epoch + 1:2d}: mean validation accuracy {score:.2f}%  ({time.time() - t0:.0f}s)", flush=True)
        for p, b in zip(ps, best_state):
            p[:] = b
        return best


def image_logits(head: Head, X, y, image, view):
    """Average the standard and mirrored view of each image (test-time augmentation)."""
    z = head.logits(X)
    n = int(image.max()) + 1
    out = np.zeros((n, N_CLASSES), np.float32)
    cnt = np.zeros(n)
    labels = np.zeros(n, np.int64)
    np.add.at(out, image, z)
    np.add.at(cnt, image, 1)
    labels[image] = y
    keep = cnt > 0
    return out[keep] / cnt[keep, None], labels[keep]


def top_k(head: Head, X, y, image, view, crop_known=False):
    z, labels = image_logits(head, X, y, image, view)
    if crop_known:  # the farmer told us the crop: only that crop's classes compete
        crop_idx = np.array([CROPS.index(CROP_OF[t]) for t in labels])
        z = np.where(CROP_MASK[crop_idx], z, -1e9)
    order = np.argsort(-z, axis=1)
    top1 = float((order[:, 0] == labels).mean() * 100)
    top3 = float((order[:, :3] == labels[:, None]).any(1).mean() * 100)
    return round(top1, 1), round(top3, 1)


def fit_temperature(z, y):
    """One number that makes the stated confidence match how often the model is right."""
    best_t, best_nll = 1.0, 1e9
    for t in np.linspace(0.5, 5, 46):
        p = softmax(z / t)
        nll = -np.log(p[np.arange(len(y)), y] + 1e-9).mean()
        if nll < best_nll:
            best_t, best_nll = float(t), nll
    return best_t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", type=Path, required=True)
    ap.add_argument("--epochs", type=int, default=30)
    args = ap.parse_args()

    data = {(s, sp): load(args.features, s, sp) for s in SOURCES for sp in ("train", "val", "test")}
    counts = {s: {sp: int(len(np.unique(data[(s, sp)][2]))) for sp in ("train", "val", "test")} for s in SOURCES}
    print("images:", counts)

    def stack(sources):
        X = np.concatenate([data[(s, "train")][0] for s in sources])
        y = np.concatenate([data[(s, "train")][1] for s in sources])
        src = np.concatenate([np.full(len(data[(s, "train")][1]), i) for i, s in enumerate(sources)])
        return X, y, src

    def balanced_p(y, src, share):
        """Sampling weights: each source gets a fixed share of every batch, classes evened out within it."""
        p = np.zeros(len(y))
        for i, frac in enumerate(share):
            k = src == i
            class_n = np.bincount(y[k], minlength=N_CLASSES).astype(float)
            w = 1.0 / np.sqrt(class_n[y[k]])  # soften, not remove, class imbalance
            p[k] = frac * w / w.sum()
        return p / p.sum()

    val = {s: data[(s, "val")] for s in SOURCES}
    results, heads = {}, {}

    def evaluate(head):
        out = {}
        for s in SOURCES:
            t1, t3 = top_k(head, *data[(s, "test")])
            k1, k3 = top_k(head, *data[(s, "test")], crop_known=True)
            out[s] = {"top1": t1, "top3": t3, "top1_crop_known": k1, "top3_crop_known": k3,
                      "images": counts[s]["test"]}
        return out

    # --- A: what most tutorials do - PlantVillage lab photos only
    print("A. lab photos only (PlantVillage), linear classifier")
    X, y, src = stack(["plantvillage"])
    mean, std = X[::7].astype(np.float32).mean(0), X[::7].astype(np.float32).std(0) + 1e-3
    head = Head(0, mean, std)
    head.fit(X, y, balanced_p(y, src, [1.0]), {"plantvillage": val["plantvillage"]}, epochs=8, drop=0, lr=2e-3)
    results["A. PlantVillage only (lab photos)"] = evaluate(head)
    results["A. PlantVillage only (lab photos)"]["paddy"] = None  # it has never seen rice
    print("   ", results["A. PlantVillage only (lab photos)"])
    del X, y, src

    # --- B: all three sets, each given a fixed share of every batch
    print("B. lab + field photos, small neural network")
    X, y, src = stack(SOURCES)
    mean, std = X[::7].astype(np.float32).mean(0), X[::7].astype(np.float32).std(0) + 1e-3
    head = Head(512, mean, std)
    head.fit(X, y, balanced_p(y, src, [0.4, 0.3, 0.3]), val, epochs=args.epochs)
    results["B. Lab + field photos (used in the app)"] = evaluate(head)
    print("   ", results["B. Lab + field photos (used in the app)"])

    # --- confidence: temperature fitted on validation images, then "how sure is sure enough?"
    zs, ys = zip(*[image_logits(head, *val[s])[:2] for s in SOURCES])
    head.T = fit_temperature(np.concatenate(zs), np.concatenate(ys))
    conf_table = []
    field = [image_logits(head, *data[(s, "test")])[:2] for s in ("plantdoc", "paddy")]
    zf, yf = np.concatenate([f[0] for f in field]), np.concatenate([f[1] for f in field])
    pf = softmax(zf / head.T)
    for thr in (0.0, 0.4, 0.5, 0.6, 0.7, 0.8):
        k = pf.max(1) >= thr
        conf_table.append({"min_confidence": thr, "answered_pct": round(float(k.mean() * 100), 1),
                           "correct_pct": round(float((pf[k].argmax(1) == yf[k]).mean() * 100), 1)})
    print("    temperature", head.T, conf_table)

    per_class = {}
    for s in SOURCES:
        z, labels = image_logits(head, *data[(s, "test")])
        pred = z.argmax(1)
        for c in np.unique(labels):
            k = labels == c
            per_class.setdefault(CLASSES[c], {})[s] = {"n": int(k.sum()), "correct_pct": round(float((pred[k] == c).mean() * 100), 1)}

    np.savez_compressed(BACKEND / "models" / "disease_head.npz", W1=head.W1.astype(np.float16), b1=head.b1,
                        W2=head.W2, b2=head.b2, mean=head.mean, std=head.std, T=np.float32(head.T))
    (BACKEND / "models" / "disease_classes.json").write_text(json.dumps(CLASSES))
    metrics = {
        "images": counts, "classes": N_CLASSES,
        "backbone": "MobileNetV2 pretrained on ImageNet (ONNX Model Zoo), frozen",
        "head": "1280 -> 512 -> 48 neural network, trained on features of 3 datasets",
        "test_note": "Test images were never used for training or tuning. PlantVillage: a random 10% hold-out "
                     "(same leaves can appear in several photos, so this number is optimistic). PlantDoc: the "
                     "dataset's own test split. Paddy Doctor: the repository's test split.",
        "results": results, "confidence_on_field_photos": conf_table, "temperature": head.T, "per_class": per_class,
    }
    (BACKEND / "models" / "disease_metrics.json").write_text(json.dumps(metrics, indent=1))
    print("saved models/disease_head.npz")


if __name__ == "__main__":
    main()
