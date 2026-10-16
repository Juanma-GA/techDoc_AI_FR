from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import TYPE_CHECKING, Any

import requests
import truststore

from app.config import settings
from app.services.constants import OCR_DETECTION_MAX_SIDE

truststore.inject_into_ssl()

# Paddle's one-second host probes can reject reachable servers behind a proxy.
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
os.environ.setdefault("PADDLE_PDX_MODEL_SOURCE", "bos")

if TYPE_CHECKING:
    from paddleocr import PaddleOCR


_OCR_MODEL_NAMES = {
    "medium": ("PP-OCRv6_medium_det", "PP-OCRv6_medium_rec"),
    "small": ("PP-OCRv6_small_det", "PP-OCRv6_small_rec"),
    "tiny": ("PP-OCRv6_tiny_det", "PP-OCRv6_tiny_rec"),
}
_ACTIVE_OCR_TIMINGS: ContextVar[dict[str, float] | None] = ContextVar(
    "active_ocr_timings", default=None
)


class _TimedModel:
    def __init__(self, model: Callable[..., object], timing_key: str) -> None:
        self._model = model
        self._timing_key = timing_key

    def __getattr__(self, name: str) -> object:
        return getattr(self._model, name)

    def __call__(self, *args: object, **kwargs: object) -> object:
        started = perf_counter()
        try:
            result = self._model(*args, **kwargs)
        except Exception:
            self._record_elapsed(started)
            raise

        if isinstance(result, Iterator):
            return self._measure_iterator(result, started)
        self._record_elapsed(started)
        return result

    def _measure_iterator(self, results: Iterator[object], started: float) -> Iterator[object]:
        try:
            yield from results
        finally:
            self._record_elapsed(started)

    def _record_elapsed(self, started: float) -> None:
        timings = _ACTIVE_OCR_TIMINGS.get()
        if timings is not None:
            elapsed_ms = (perf_counter() - started) * 1000
            timings[self._timing_key] = round(timings.get(self._timing_key, 0.0) + elapsed_ms, 3)


def _instrument_ocr_stages(engine: PaddleOCR) -> None:
    pipeline = getattr(engine, "paddlex_pipeline", None)
    if pipeline is None:
        raise RuntimeError("PaddleOCR n'expose pas son pipeline pour mesurer les étapes OCR.")

    for attribute, timing_key in (
        ("text_det_model", "ocr_detection_ms"),
        ("textline_orientation_model", "ocr_orientation_ms"),
        ("text_rec_model", "ocr_recognition_ms"),
    ):
        model = getattr(pipeline, attribute, None)
        if not callable(model):
            raise RuntimeError(f"Le pipeline PaddleOCR n'expose pas le modèle {attribute}.")
        setattr(pipeline, attribute, _TimedModel(model, timing_key))


@contextmanager
def _capture_ocr_stage_timings(timings: dict[str, float] | None) -> Iterator[None]:
    token = _ACTIVE_OCR_TIMINGS.set(timings)
    try:
        yield
    finally:
        _ACTIVE_OCR_TIMINGS.reset(token)


@lru_cache(maxsize=1)
def get_ocr_engine() -> PaddleOCR:
    from paddleocr import PaddleOCR

    detection_model, recognition_model = _OCR_MODEL_NAMES[settings.ocr_model_variant]
    original_get = requests.get

    def get_with_model_download_timeout(
        url: str, *args: Any, **kwargs: Any
    ) -> requests.Response:
        if kwargs.get("stream") is True and kwargs.get("timeout") == 15:
            kwargs["timeout"] = (15, 120)
        return original_get(url, *args, **kwargs)

    requests.get = get_with_model_download_timeout  # type: ignore[assignment]
    try:
        engine = PaddleOCR(
            text_detection_model_name=detection_model,
            text_recognition_model_name=recognition_model,
            device="cpu",
            cpu_threads=settings.ocr_cpu_threads,
            enable_mkldnn=False,
            text_det_limit_side_len=OCR_DETECTION_MAX_SIDE,
            text_det_limit_type="max",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=True,
            textline_orientation_model_name="PP-LCNet_x1_0_textline_ori",
            # PaddleX can expose batch-wide class IDs for each individual result.
            textline_orientation_batch_size=1,
        )
    finally:
        requests.get = original_get

    _instrument_ocr_stages(engine)
    return engine


def run_ocr_on_image(image_bytes: bytes, timings: dict[str, float] | None = None) -> object:
    with TemporaryDirectory() as temporary_directory:
        image_path = Path(temporary_directory) / "image.png"
        stage_started = perf_counter()
        image_path.write_bytes(image_bytes)
        if timings is not None:
            timings["ocr_temp_write_ms"] = round((perf_counter() - stage_started) * 1000, 3)

        stage_started = perf_counter()
        engine = get_ocr_engine()
        if timings is not None:
            timings["ocr_engine_access_ms"] = round((perf_counter() - stage_started) * 1000, 3)

        stage_started = perf_counter()
        with _capture_ocr_stage_timings(timings):
            predictions = iter(engine.predict(input=str(image_path)))
            prediction = next(predictions, None)
        if timings is not None:
            timings["ocr_predict_ms"] = round((perf_counter() - stage_started) * 1000, 3)
        if prediction is None:
            raise RuntimeError("PaddleOCR n'a renvoyé aucun résultat pour cette image.")
        return prediction
