from __future__ import annotations

import base64
from io import BytesIO
from time import perf_counter

import structlog
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from app.config import settings
from app.services.constants import (
    A4_DPI,
    A4_HEIGHT,
    A4_WIDTH,
    MAX_IMAGE_BYTES,
    MAX_REPLACEMENT_FONT_SIZE,
    SUPPORTED_FORMATS,
)
from app.services.excel import (
    extract_excel_replacements,
    get_excel_sheet,
    open_excel_workbook,
    read_excel_upload,
)
from app.services.image_layout import create_a4_page, output_filename, prepare_source_image
from app.services.image_replacement import apply_replacements
from app.services.ocr_engine import (
    _build_lines,
    _match_references,
    _parse_replacement_pairs,
    normalize_reference,
)
from app.services.ocr_inference import run_ocr_on_image

router = APIRouter(prefix="/image-processor", tags=["image-processor"])
log = structlog.get_logger(__name__)


def _elapsed_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)


@router.post("/ocr")
async def run_ocr(
    image: UploadFile = File(...),
    references: str = Form(default=""),
    replacement_pairs: str | None = Form(default=None),
    excel_replacement_pairs: str | None = Form(default=None),
    workbook: UploadFile | None = File(default=None),
    excel_sheet: str | None = Form(default=None),
    excel_reference_column: int | None = Form(default=None),
    excel_replacement_column: int | None = Form(default=None),
    excel_icn_column: int | None = Form(default=None),
    excel_piece_column: int | None = Form(default=None),
    excel_piece_row: int | None = Form(default=None),
    replacement_font_size: int | None = Form(default=None, ge=1, le=MAX_REPLACEMENT_FONT_SIZE),
) -> dict[str, object]:
    total_started = perf_counter()
    timings: dict[str, float] = {}
    stage_started = perf_counter()
    image_bytes = await image.read(MAX_IMAGE_BYTES + 1)
    timings["upload_read_ms"] = _elapsed_ms(stage_started)
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="L'image dépasse la limite de 15 Mo.")
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Le fichier image est vide.")

    stage_started = perf_counter()
    replacement_list = _parse_replacement_pairs(replacement_pairs) if replacement_pairs is not None else []
    if replacement_pairs is not None or workbook is not None:
        reference_list = [pair["reference"] for pair in replacement_list]
    else:
        reference_list = [value.strip() for value in references.splitlines() if value.strip()]

    excel_parameters = (
        excel_sheet,
        excel_reference_column,
        excel_replacement_column,
        excel_icn_column,
        excel_piece_column,
        excel_piece_row,
    )
    if workbook is None and (
        any(value is not None for value in excel_parameters)
        or excel_replacement_pairs is not None
    ):
        raise HTTPException(status_code=422, detail="Le fichier Excel est requis pour ces sélections.")
    if workbook is not None and any(value is None for value in excel_parameters):
        raise HTTPException(status_code=422, detail="Sélectionne l'onglet, les colonnes et la pièce Excel.")

    output_icn: str | None = None
    if workbook is not None:
        workbook_bytes = await read_excel_upload(workbook)
        with open_excel_workbook(workbook_bytes, workbook.filename) as excel_workbook:
            worksheet = get_excel_sheet(excel_workbook, excel_sheet or "")
            excel_replacements, output_icn = extract_excel_replacements(
                worksheet,
                excel_reference_column or 0,
                excel_replacement_column or 0,
                excel_icn_column or 0,
                excel_piece_column or 0,
                excel_piece_row or 0,
            )
            if excel_replacement_pairs is not None:
                excel_replacements = _parse_replacement_pairs(excel_replacement_pairs)

        for pair in excel_replacements:
            replacement_list.append(pair)
            reference_list.append(pair["reference"])

    if any(not normalize_reference(value) for value in reference_list):
        raise HTTPException(
            status_code=422,
            detail="Chaque référence doit contenir au moins une lettre ou un chiffre.",
        )
    timings["form_setup_ms"] = _elapsed_ms(stage_started)

    stage_started = perf_counter()
    try:
        with Image.open(BytesIO(image_bytes)) as image_data:
            image_format = image_data.format
            image_data.verify()
    except (UnidentifiedImageError, OSError) as error:
        raise HTTPException(
            status_code=400, detail="Le fichier fourni n'est pas une image valide."
        ) from error

    if SUPPORTED_FORMATS.get(image_format or "") is None:
        raise HTTPException(status_code=415, detail="Formats acceptés : PNG, JPEG, WEBP, BMP et TIFF.")
    timings["image_verify_ms"] = _elapsed_ms(stage_started)

    stage_started = perf_counter()
    try:
        source_canvas, ocr_image_bytes = prepare_source_image(image_bytes)
    except (UnidentifiedImageError, OSError) as error:
        raise HTTPException(
            status_code=400, detail="Le fichier fourni n'est pas une image valide."
        ) from error
    timings["image_prepare_ms"] = _elapsed_ms(stage_started)
    width, height = source_canvas.size

    ocr_timings: dict[str, float] = {}
    stage_started = perf_counter()
    prediction = run_ocr_on_image(ocr_image_bytes, timings=ocr_timings)
    timings["ocr_pipeline_ms"] = _elapsed_ms(stage_started)

    stage_started = perf_counter()
    lines, matches = _match_references(_build_lines(prediction), reference_list)
    output_image, scale_x, scale_y, offset_x, offset_y = create_a4_page(source_canvas)
    for line in lines:
        line["box"] = [
            [point[0] * scale_x + offset_x, point[1] * scale_y + offset_y] for point in line["box"]
        ]
    output_image, applied_counts, font_size = apply_replacements(
        output_image, lines, replacement_list, replacement_font_size,
    )
    for match, pair, applied_count in zip(matches, replacement_list, applied_counts, strict=False):
        match["replacement"] = pair["replacement"]
        match["replacement_count"] = applied_count
    timings["replacement_layout_ms"] = _elapsed_ms(stage_started)

    stage_started = perf_counter()
    output = BytesIO()
    output_image.save(output, format="JPEG", quality=95, optimize=True, dpi=(A4_DPI, A4_DPI))
    jpeg_bytes = output.getvalue()
    timings["jpeg_encode_ms"] = _elapsed_ms(stage_started)

    stage_started = perf_counter()
    encoded_image = base64.b64encode(jpeg_bytes).decode("ascii")
    timings["base64_encode_ms"] = _elapsed_ms(stage_started)
    response_payload = {
        "width": A4_WIDTH,
        "height": A4_HEIGHT,
        "source_width": width,
        "source_height": height,
        "full_text": "\n".join(str(line["text"]) for line in lines),
        "lines": lines,
        "references": matches,
        "edited_image": f"data:image/jpeg;base64,{encoded_image}",
        "filename": output_filename(image.filename, output_icn),
        "replacement_font_size": font_size,
    }
    log.info(
        "image_ocr_timing",
        total_ms=_elapsed_ms(total_started),
        input_bytes=len(image_bytes),
        ocr_input_bytes=len(ocr_image_bytes),
        source_width=width,
        source_height=height,
        ocr_model_variant=settings.ocr_model_variant,
        ocr_cpu_threads=settings.ocr_cpu_threads,
        detected_lines=len(lines),
        reference_count=len(reference_list),
        replacement_pair_count=len(replacement_list),
        **timings,
        **ocr_timings,
    )
    return response_payload
