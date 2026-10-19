"""Validate self-contained local files without accessing application storage."""

from __future__ import annotations

import base64
import binascii
from hashlib import sha256
from io import BytesIO

from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.services.constants import MAX_IMAGE_BYTES, SUPPORTED_FORMATS
from app.services.excel import open_excel_workbook


class StoredFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    data_url: str = Field(max_length=((MAX_IMAGE_BYTES + 2) // 3) * 4 + 150)
    sha256: str = ""

    def contents(self) -> bytes:
        header, separator, encoded = self.data_url.partition(",")
        if not separator or not header.startswith("data:") or not header.endswith(";base64"):
            raise ValueError("Expected a base64 file data URL.")
        try:
            contents = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as error:
            raise ValueError("Invalid base64 file.") from error
        if not contents or len(contents) > MAX_IMAGE_BYTES:
            raise ValueError("Files must contain between 1 byte and 15 MB.")
        return contents

    @model_validator(mode="after")
    def validate_digest(self) -> StoredFile:
        digest = sha256(self.contents()).hexdigest()
        if self.sha256 and self.sha256 != digest:
            raise ValueError("Saved file checksum mismatch.")
        self.sha256 = digest
        return self


class SavedImage(StoredFile):
    @model_validator(mode="after")
    def validate_image(self) -> SavedImage:
        try:
            with Image.open(BytesIO(self.contents())) as image:
                if image.format not in SUPPORTED_FORMATS:
                    raise ValueError("Unsupported image format.")
                mime = f"image/{image.format.lower()}"
                allowed = {f"data:{mime};base64"}
                if image.format == "TIFF":
                    allowed.add("data:image/x-tiff;base64")
                if self.data_url.partition(",")[0] not in allowed:
                    raise ValueError("Image MIME type does not match its contents.")
                image.verify()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
            raise ValueError("Invalid saved image.") from error
        return self


class SavedWorkbook(StoredFile):
    @model_validator(mode="after")
    def validate_workbook(self) -> SavedWorkbook:
        mime = self.data_url.partition(",")[0].lower()
        if mime not in {
            "data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64",
            "data:application/vnd.ms-excel.sheet.macroenabled.12;base64",
            "data:application/vnd.ms-excel;base64",
            "data:application/octet-stream;base64",
        }:
            raise ValueError("Unsupported workbook MIME type.")
        with open_excel_workbook(self.contents(), self.name):
            pass
        return self
