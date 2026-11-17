"""Cut the ImageNet classifier off the ONNX Model Zoo MobileNetV2 so it outputs features.

Input : mobilenetv2-12.onnx from https://github.com/onnx/models (Apache-2.0)
Output: models/mobilenetv2_features.onnx  (image batch -> pooled 1280-d features)

    python -m ml.build_backbone path/to/mobilenetv2-12.onnx
"""
import sys
from pathlib import Path

import onnx
from onnx import utils

OUT = Path(__file__).resolve().parent.parent / "models" / "mobilenetv2_features.onnx"


def main(src: str) -> None:
    model = onnx.load(src)
    pool = [n for n in model.graph.node if n.op_type == "GlobalAveragePool"]
    assert len(pool) == 1, "expected exactly one global pooling layer"
    feature_name = pool[0].output[0]
    input_name = model.graph.input[0].name
    OUT.parent.mkdir(parents=True, exist_ok=True)
    utils.extract_model(src, str(OUT), [input_name], [feature_name])
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB), output tensor '{feature_name}'")


if __name__ == "__main__":
    main(sys.argv[1])
