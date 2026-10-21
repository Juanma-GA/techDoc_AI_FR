from fastapi import APIRouter

from app.api import (
    admin,
    analyze,
    documents,
    health,
    metadata_suggestions,
    preparation,
    preparation_ocr,
    preparation_rules,
    rules,
    settings as settings_api,
    standards,
    suggestions,
)

api_v1 = APIRouter()
for module in (
    health,
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
