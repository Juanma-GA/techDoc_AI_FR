from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from app.config import settings
from app.core.errors import AppError
from app.core.ocr_output import extract_result
from app.core.ocr_types import OcrBox


def local_provider_available(provider: str) -> bool:
    if provider == "paddle":
        return _paddleocr_python() is not None
    if provider == "indra":
        return shutil.which("indra-ocr") is not None
    return False


def _paddleocr_python() -> str | None:
    configured = settings.paddleocr_python.strip()
    if not configured:
        try:
            if importlib.util.find_spec("paddleocr") and importlib.util.find_spec("paddle"):
                return sys.executable
        except (ImportError, ValueError):
            return None
        return None
    executable = Path(configured).expanduser()
    return str(executable) if executable.is_file() else None


def run_paddle_ocr(
    image_bytes: bytes,
    image_width: int,
    image_height: int,
) -> tuple[str, list[OcrBox]]:
    python_executable = _paddleocr_python()
    if not python_executable:
        if settings.paddleocr_python.strip():
            raise AppError(
                "PADDLEOCR_PYTHON_NOT_FOUND",
                "L'interpréteur Python configuré pour PaddleOCR est introuvable.",
                status_code=503,
            )
        raise _not_installed("PaddleOCR")
    with tempfile.TemporaryDirectory(prefix="doc-reviewer-ocr-") as temp_dir:
        image_path = Path(temp_dir) / "page.png"
        output_dir = Path(temp_dir) / "output"
        output_dir.mkdir()
        image_path.write_bytes(image_bytes)
        output_path = output_dir / "page_res.json"
        _run_command(
            [
                python_executable,
                str(Path(__file__).resolve().parents[2] / "app" / "paddleocr_worker.py"),
                "--image",
                str(image_path),
                "--output",
                str(output_path),
                "--cpu-threads",
                str(settings.paddleocr_cpu_threads),
            ],
            "PaddleOCR",
        )
        try:
            payload = json.loads(output_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise AppError(
                "PADDLEOCR_RESPONSE_INVALID",
                "PaddleOCR n'a pas produit le JSON de résultat attendu.",
                status_code=502,
            ) from exc
    return extract_result(
        payload,
        image_width,
        image_height,
        coordinate_mode="pixels",
    )


def run_indra_ocr(
    image_bytes: bytes,
    image_width: int,
    image_height: int,
) -> tuple[str, list[OcrBox]]:
    executable = shutil.which("indra-ocr")
    if not executable:
        raise _not_installed("Indra OCR")
    with tempfile.TemporaryDirectory(prefix="doc-reviewer-ocr-") as temp_dir:
        image_path = Path(temp_dir) / "page.png"
        image_path.write_bytes(image_bytes)
        env = os.environ.copy()
        env["HF_HUB_OFFLINE"] = "1"
        env["HF_HUB_DISABLE_TELEMETRY"] = "1"
        output = _run_command(
            [executable, str(image_path), "--format", "json"],
            "Indra OCR",
            env=env,
        )
    try:
        payload = json.loads(output)
    except ValueError as exc:
        raise AppError(
            "INDRA_OCR_RESPONSE_INVALID",
            "Indra OCR n'a pas produit un JSON valide.",
            status_code=502,
        ) from exc
    return extract_result(
        payload,
        image_width,
        image_height,
        coordinate_mode="pixels",
    )


def _run_command(
    command: list[str],
    provider: str,
    *,
    env: dict[str, str] | None = None,
) -> str:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise AppError(
            "OCR_PROVIDER_TIMEOUT",
            f"{provider} n'a pas terminé dans le délai autorisé.",
            status_code=504,
        ) from exc
    except OSError as exc:
        raise AppError(
            "OCR_PROVIDER_START_FAILED",
            f"Impossible de démarrer {provider} : {type(exc).__name__}.",
            status_code=503,
        ) from exc
    if result.returncode != 0:
        raise AppError(
            "OCR_PROVIDER_FAILED",
            f"{provider} a échoué (code {result.returncode}).",
            status_code=502,
            detail={"stderr": result.stderr[-500:]},
        )
    return result.stdout


def _not_installed(provider: str) -> AppError:
    return AppError(
        f"{provider.upper().replace(' ', '_')}_NOT_INSTALLED",
        f"{provider} n'est pas disponible dans le PATH du backend.",
        status_code=503,
    )
