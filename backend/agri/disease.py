"""Leaf photo -> likely condition, with confidence and treatment."""
from __future__ import annotations

import json
from functools import lru_cache

import numpy as np

from .config import MODELS_DIR
from .diseases_kb import DISEASES, KISAN_CALL_CENTRE
from .vision import FeatureExtractor, flipped_view, load_image, standard_view

# crop ids used by the app -> crop prefix used by the classifier
APP_TO_MODEL_CROP = {"rice": "rice", "maize": "maize", "potato": "potato", "tomato": "tomato", "chilli": "pepper",
                     "soybean": "soybean"}
MODEL_CROPS = {"apple": "Apple", "blueberry": "Blueberry", "cherry": "Cherry", "citrus": "Citrus / orange",
               "grape": "Grape", "maize": "Maize", "peach": "Peach", "pepper": "Capsicum / chilli", "potato": "Potato",
               "raspberry": "Raspberry", "rice": "Rice", "soybean": "Soybean", "squash": "Gourds / squash",
               "strawberry": "Strawberry", "tomato": "Tomato"}
UNSURE = 0.5


class DiseaseModel:
    def __init__(self):
        z = np.load(MODELS_DIR / "disease_head.npz")
        self.W1, self.b1 = z["W1"].astype(np.float32), z["b1"]
        self.W2, self.b2 = z["W2"], z["b2"]
        self.mean, self.std, self.T = z["mean"], z["std"], float(z["T"])
        self.classes = json.loads((MODELS_DIR / "disease_classes.json").read_text())
        self.crop_of = [c.split("_")[0] for c in self.classes]
        self.fx = FeatureExtractor(threads=2)

    def predict(self, image_bytes: bytes, crop: str | None = None) -> dict:
        img = load_image(image_bytes)
        batch = np.stack([standard_view(img), flipped_view(img)])
        feats = (self.fx(batch) - self.mean) / self.std
        logits = (np.maximum(feats @ self.W1 + self.b1, 0) @ self.W2 + self.b2).mean(0) / self.T
        model_crop = APP_TO_MODEL_CROP.get(crop, crop) if crop else None
        if model_crop in MODEL_CROPS:
            logits = np.where(np.array(self.crop_of) == model_crop, logits, -1e9)
        p = np.exp(logits - logits.max())
        p /= p.sum()
        order = np.argsort(-p)[:3]
        top = [{"id": self.classes[i], "crop": MODEL_CROPS[self.crop_of[i]], "confidence": round(float(p[i]), 3),
                **{k: DISEASES[self.classes[i]][k] for k in ("name", "kind", "severity")}} for i in order]
        best = top[0]
        # crop totals tell us which plant the model thinks this is
        crop_p = {}
        for i, c in enumerate(self.crop_of):
            crop_p[c] = crop_p.get(c, 0.0) + float(p[i])
        seen_crop = max(crop_p, key=crop_p.get)
        return {
            "result": {**best, **DISEASES[best["id"]]},
            "alternatives": top[1:],
            "unsure": best["confidence"] < UNSURE,
            "crop_used": model_crop if model_crop in MODEL_CROPS else None,
            "crop_seen": {"id": seen_crop, "name": MODEL_CROPS[seen_crop], "confidence": round(crop_p[seen_crop], 3)},
            "helpline": KISAN_CALL_CENTRE,
        }


@lru_cache(maxsize=1)
def model() -> DiseaseModel:
    return DiseaseModel()


def supported_crops() -> list[dict]:
    return [{"id": k, "name": v} for k, v in MODEL_CROPS.items()]
