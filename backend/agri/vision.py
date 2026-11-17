"""Image preprocessing and the frozen feature extractor used by the leaf-disease model.

The same functions are used when training (ml/extract_features.py) and when the app
scores a photo, so both see identical pixels.
"""
from __future__ import annotations

import io
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

IMAGE_SIZE = 224
RESIZE_TO = 256
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
BACKBONE_PATH = MODELS_DIR / "mobilenetv2_features.onnx"


def load_image(source) -> Image.Image:
    """Open a path, bytes or file object as an upright RGB image."""
    if isinstance(source, (bytes, bytearray)):
        source = io.BytesIO(source)
    img = Image.open(source)
    # Let the JPEG decoder downscale very large photos while decoding (much faster).
    try:
        img.draft("RGB", (RESIZE_TO * 2, RESIZE_TO * 2))
    except Exception:
        pass
    img = ImageOps.exif_transpose(img)
    return img.convert("RGB")


def resize_shorter(img: Image.Image, size: int = RESIZE_TO) -> Image.Image:
    w, h = img.size
    scale = size / min(w, h)
    nw, nh = max(size, round(w * scale)), max(size, round(h * scale))
    return img.resize((nw, nh), Image.BILINEAR)


def center_crop(img: Image.Image, size: int = IMAGE_SIZE) -> Image.Image:
    w, h = img.size
    left, top = (w - size) // 2, (h - size) // 2
    return img.crop((left, top, left + size, top + size))


def to_tensor(img: Image.Image) -> np.ndarray:
    """224x224 RGB image -> normalised float32 array shaped (3, 224, 224)."""
    arr = np.asarray(img, dtype=np.float32) / 255.0
    arr = (arr - _MEAN) / _STD
    return np.ascontiguousarray(arr.transpose(2, 0, 1))


def standard_view(img: Image.Image) -> np.ndarray:
    return to_tensor(center_crop(resize_shorter(img)))


def flipped_view(img: Image.Image) -> np.ndarray:
    return to_tensor(ImageOps.mirror(center_crop(resize_shorter(img))))


def random_crop_view(img: Image.Image, rng: np.random.Generator) -> np.ndarray:
    """A random 55-100% area crop, resized to 224 and randomly mirrored (training only)."""
    w, h = img.size
    area = w * h * rng.uniform(0.55, 1.0)
    ratio = rng.uniform(3 / 4, 4 / 3)
    cw = int(min(w, round((area * ratio) ** 0.5)))
    ch = int(min(h, round((area / ratio) ** 0.5)))
    left = int(rng.integers(0, w - cw + 1))
    top = int(rng.integers(0, h - ch + 1))
    crop = img.crop((left, top, left + cw, top + ch)).resize((IMAGE_SIZE, IMAGE_SIZE), Image.BILINEAR)
    if rng.random() < 0.5:
        crop = ImageOps.mirror(crop)
    return to_tensor(crop)


class FeatureExtractor:
    """MobileNetV2 (ImageNet weights) with the classifier removed: image -> 1280 numbers."""

    def __init__(self, path: Path | str = BACKBONE_PATH, threads: int = 2):
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = threads
        opts.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(path), opts, providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name

    def __call__(self, batch: np.ndarray) -> np.ndarray:
        out = self.session.run(None, {self.input_name: batch.astype(np.float32, copy=False)})[0]
        return out.reshape(out.shape[0], -1)
