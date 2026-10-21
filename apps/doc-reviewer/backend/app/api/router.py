from fastapi import APIRouter

from app.api import (
    admin,
    analyze,
    comparison_exports,
    comparison_pages,
    comparison_synthesis,
    comparisons,
    documents,
    health,
    metadata_suggestions,
    preparation,
    preparation_ocr,
    preparation_rules,
    rules,
    standards,
    suggestions,
)
from app.api import settings as settings_api

api_v1 = APIRouter()
for module in (
    health,
    comparisons,
    comparison_synthesis,
    comparison_exports,
    comparison_pages,
    documents,
    metadata_suggestions,
    analyze,
    preparation,
    preparation_ocr,
    preparation_rules,
    suggestions,
    rules,
    standards,
    settings_api,
    admin,
):
    api_v1.include_router(module.router)
