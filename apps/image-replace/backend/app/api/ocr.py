from __future__ import annotations

import base64
from io import BytesIO

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from app.services.constants import A4_DPI, A4_HEIGHT, A4_WIDTH, MAX_IMAGE_BYTES, SUPPORTED_FORMATS
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
    run_ocr_on_image,
)

router = APIRouter(prefix="/image-replace", tags=["image-replace"])


@router.post("/ocr")
async def run_ocr(
    image: UploadFile = File(...),
    references: str = Form(default=""),
    replacement_pairs: str | None = Form(default=None),
    workbook: UploadFile | None = File(default=None),
    excel_sheet: str | None = Form(default=None),
    excel_reference_column: int | None = Form(default=None),
    excel_replacement_column: int | None = Form(default=None),
    excel_icn_column: int | None = Form(default=None),
    excel_piece_column: int | None = Form(default=None),
    excel_piece_row: int | None = Form(default=None),
) -> dict[str, object]:
    image_bytes = await image.read(MAX_IMAGE_BYTES + 1)
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="L'image dépasse la limite de 15 Mo.")
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Le fichier image est vide.")

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
    if workbook is None and any(value is not None for value in excel_parameters):
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

        seen_references = {normalize_reference(pair["reference"]) for pair in replacement_list}
        for pair in excel_replacements:
            normalized_reference = normalize_reference(pair["reference"])
            if normalized_reference in seen_references:
                raise HTTPException(
                    status_code=422,
                    detail="Une même référence ne peut pas apparaître plusieurs fois dans les remplacements.",
                )
            seen_references.add(normalized_reference)
            replacement_list.append(pair)
            reference_list.append(pair["reference"])

    if any(not normalize_reference(value) for value in reference_list):
        raise HTTPException(
            status_code=422,
            detail="Chaque référence doit contenir au moins une lettre ou un chiffre.",
        )

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

    try:
        source_canvas, ocr_image_bytes = prepare_source_image(image_bytes)
    except (UnidentifiedImageError, OSError) as error:
        raise HTTPException(
            status_code=400, detail="Le fichier fourni n'est pas une image valide."
        ) from error
    width, height = source_canvas.size

    prediction = run_ocr_on_image(ocr_image_bytes)

    lines, matches = _match_references(_build_lines(prediction), reference_list)
    edited_canvas, applied_counts = apply_replacements(source_canvas, lines, replacement_list)
    for match, pair, applied_count in zip(matches, replacement_list, applied_counts, strict=False):
        match["replacement"] = pair["replacement"]
        match["replacement_count"] = applied_count

    output_image, scale_x, scale_y, offset_x, offset_y = create_a4_page(edited_canvas)
    for line in lines:
        line["box"] = [
            [point[0] * scale_x + offset_x, point[1] * scale_y + offset_y] for point in line["box"]
        ]

    output = BytesIO()
    output_image.save(output, format="JPEG", quality=95, optimize=True, dpi=(A4_DPI, A4_DPI))

    encoded_image = base64.b64encode(output.getvalue()).decode("ascii")
    return {
        "width": A4_WIDTH,
        "height": A4_HEIGHT,
        "source_width": width,
        "source_height": height,
        "full_text": "\n".join(str(line["text"]) for line in lines),
        "lines": lines,
        "references": matches,
        "edited_image": f"data:image/jpeg;base64,{encoded_image}",
        "filename": output_filename(image.filename, output_icn),
    }
