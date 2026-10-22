from __future__ import annotations

import argparse
import os
from pathlib import Path

os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
os.environ.setdefault("PADDLE_PDX_MODEL_SOURCE", "bos")

from paddleocr import PaddleOCR


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cpu-threads", default=10, type=int)
    args = parser.parse_args()

    engine = PaddleOCR(
        text_detection_model_name="PP-OCRv6_tiny_det",
        text_recognition_model_name="PP-OCRv6_tiny_rec",
        device="cpu",
        cpu_threads=args.cpu_threads,
        enable_mkldnn=False,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=True,
        textline_orientation_model_name="PP-LCNet_x1_0_textline_ori",
        textline_orientation_batch_size=1,
        text_det_limit_side_len=1600,
        text_det_limit_type="max",
    )
    prediction = next(iter(engine.predict(input=str(args.image))), None)
    if prediction is None:
        raise RuntimeError("PaddleOCR n'a renvoyé aucun résultat pour cette image.")
    prediction.save_to_json(str(args.output))


if __name__ == "__main__":
    main()
